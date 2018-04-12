#!/usr/bin/env python

#    twotonedecoder.py: Decodes the frequencies of two-tone codes used in
#                       fire dispatch pager systems. 
#
#    Copyright (C) 2013 Seth Yastrov <syastrov@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


################################
# Settings
################################

# Number of tones to measure sequentially before considering as a new tone group
NUM_TONES = 2

# Minimum difference between two tone frequencies in Hz to consider them as different tones
MIN_TONE_FREQUENCY_DIFFERENCE = 4.0
MAX_TONE_FREQUENCY_DIFFERENCE = 15.0

MAX_FREQ = 3000.0
MIN_FREQ = 300.0

# Minimum length of time in seconds to consider a signal as a tone
MIN_TONE_LENGTH = 0.200

# Maximum standard deviation in tone frequency to consider a signal as one tone
MAX_TONE_FREQ_STD_DEVIATION = 10.0

# Loudness in dB, below which to ignore signals
SQUELCH = -70.

FIRE_DEPT_TONES = [435.0, 440.0]
EMS_DEPT_TONES = [467.0, 461.0]
################################
# END Settings
################################

import sys

import logging
from logging.config import fileConfig

fileConfig('logging_config.ini')
logger = logging.getLogger()
logger.debug('often makes a very good meal of %s', 'visiting tourists')

try:
    import numpy
except ImportError:
    logger.error("NumPy required to perform calculations")
    raise


def schmitt(data, rate):
    loudness = numpy.sqrt(numpy.sum((data / 32768.) ** 2)) / float(len(data))
    logger.debug("loudness: %s", loudness)
    if loudness <= 0:
        return -1

    rms = 20.0 * numpy.log10(loudness)
    logger.debug("RMS: %s", rms)
    if rms < SQUELCH:
        return -1

    blockSize = len(data) - 1

    # print blockSize
    freq = 0.
    trigfact = 0.6

    schmittBuffer = data

    A1 = max(schmittBuffer)
    A2 = min(schmittBuffer)

    # print "A1", A1, "A2", A2

    # calculate trigger values, rounding up
    t1 = round(A1 * trigfact)
    t2 = round(A2 * trigfact)

    # print "T1", t1, "T2", t2

    startpoint = -1
    endpoint = 0
    schmittTriggered = 0
    tc = 0
    schmitt = []
    for j in range(0, blockSize):
        schmitt.append(schmittTriggered)
        if not schmittTriggered:
            schmittTriggered = (schmittBuffer[j] >= t1)
        elif schmittBuffer[j] >= t2 and schmittBuffer[j + 1] < t2:
            schmittTriggered = 0
            if startpoint == -1:
                tc = 0
                startpoint = j
                endpoint = startpoint + 1
            else:
                endpoint = j
                tc += 1

    # print "Start, end", startpoint, endpoint
    # print "TC", tc
    if endpoint > startpoint:
        freq = rate * (tc / float(endpoint - startpoint))

    """
    from pylab import *
    ion()
    
    timeArray = arange(0, float(len(data)), 1)
    timeArray = timeArray / rate
    timeArray = timeArray * 1000  #scale to milliseconds
  
    hold(False)
  
    plot(timeArray, data, 'k', timeArray[startpoint:endpoint], [s*1000 for s in schmitt[startpoint:endpoint]], 'r')
    title('Frequency: %7.3f Hz' % freq)
    ylabel('Amplitude')
    xlabel('Time (ms)')
  
    draw()
    """

    return freq


class DetectTones():

    def validate_freq(self, freq):
        return (freq >= MIN_FREQ and freq <= MAX_FREQ)

    def detect_tones(self, freq1, freq2):
        span = abs(freq2 - freq1)

        logger.info("span: %s", span)

        if self.validate_freq(freq1) and self.validate_freq(freq2):

            if span >= MIN_TONE_FREQUENCY_DIFFERENCE and span <= MAX_TONE_FREQUENCY_DIFFERENCE:
                logger.info("Tones Changed: %s, %s", freq1, freq2)
                if [freq1, freq2] == FIRE_DEPT_TONES:
                    logger.critical("fire dept dispatch!")
                    return 2
                elif [freq1, freq2] == EMS_DEPT_TONES:
                    logger.critical("ems dept dispatch!")
                    return 2
                else:
                    logger.warn("possible unidentified dispatch [%s, %s]", freq1, freq2)
                    return 1
            else:
                logger.debug("not enough change")
        else:
            logger.debug("frequency out of range")

        return 0

    def detectWaveFile(self, wavfile):
        chunk = 2048
        import wave
        wav = wave.open(wavfile, 'r')

        rate = wav.getframerate()
        channels = wav.getnchannels()
        width = wav.getsampwidth()

        logger.info("channels: %d", channels)
        logger.info("width: %d", width)
        logger.info("rate: %d", rate)

        tones = [0, 0]
        mean = 0

        freqBufferSize = int(MIN_TONE_LENGTH * rate / float(chunk))
        freqBuffer = numpy.zeros(freqBufferSize)
        freqIndex = 0
        lastFreq = 0.
        toneIndex = -1

        while wav.tell() < wav.getnframes():

            data = wav.readframes(chunk)

            buf = numpy.fromstring(data, dtype=numpy.int16)

            if channels == 2:
                # Get rid of second channel
                buf = buf.reshape(-1, 2)
                buf = numpy.delete(buf, 1, axis=1)
                buf = buf.reshape(-1)

            freq = schmitt(buf, rate)
            if freq > 0:
                freqBuffer[freqIndex % freqBufferSize] = freq
                stddev = freqBuffer.std()
                logger.info("Std deviation: %s", stddev)

                if stddev < MAX_TONE_FREQ_STD_DEVIATION:
                    mean = freqBuffer.mean()
                    # Clear ringbuffer
                    # freqBuffer = numpy.zeros(freqBufferSize)
                    logger.info("Mean: %s, Last: %s", mean, lastFreq)

                    if abs(mean - lastFreq) > MIN_TONE_FREQUENCY_DIFFERENCE:
                        toneIndex = (toneIndex + 1) % NUM_TONES
                        logger.debug("tone index: %s", toneIndex)
                        if toneIndex == 0:
                            logger.debug("clear freq")
                        else:
                            logger.info("update freq: %s, %s", lastFreq, mean)
                            code = self.detect_tones(numpy.trunc(lastFreq), numpy.trunc(mean))
                            if (code > 0):
                                wav.close()
                                return code

            # lastRoundFreq = roundFreq
            lastFreq = mean

        wav.close()
        return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        wavfile = sys.argv[1]
    else:
        logger.error("no wave file provided")
        sys.exit(1)

    toneDetector = DetectTones()
    sys.exit(toneDetector.detectWaveFile(wavfile))
