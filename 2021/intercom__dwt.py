#
# Intercom
# |
# +- Intercom_buffer
#    |
#    +- Intercom_bitplanes
#       |
#       +- Intercom_binaural
#          |
#          +- Intercom_DFC
#             |
#             +- Intercom_empty
#                |
#                +- Intercom_DWT
#
# Convert the chunks of samples intro chunks of wavelet coefficients
# (coeffs in short).
#
# The coefficients require more bitplanes than the original samples,
# but most of the energy of the samples of the original chunk tends to
# be into a small number of coefficients that are localized, usually
# in the low-frequency subbands:
#
# (supposing a chunk with 1024 samples)
#
# Amplitude
#     |       +                      *
#     |   *     *                  *
#     | *        *                *
#     |*          *             *
#     |             *       *
#     |                 *
#     +------------------------------- Time
#     0                  ^        1023 
#                |       |       
#               DWT  Inverse DWT 
#                |       |
#                v
# Amplitude
#     |*
#     |
#     | *
#     |  **
#     |    ****
#     |        *******
#     |               *****************
#     +++-+---+------+----------------+ Frequency
#     0                            1023
#     ^^ ^  ^     ^           ^
#     || |  |     |           |
#     || |  |     |           +--- Subband H1 (16N coeffs)
#     || |  |     +--------------- Subband H2 (8N coeffs)
#     || |  +--------------------- Subband H3 (4N coeffs)
#     || +------------------------ Subband H4 (2N coeffs)
#     |+-------------------------- Subband H5 (N coeffs)
#     +--------------------------- Subband L5 (N coeffs)
#
# (each channel must be transformed independently)
#
# This means that the most-significant bitplanes, for most of the
# chunks (this depends on the content of the chunk), should have only
# bits different of 0 in the coeffs that belongs to the low-frequency
# subbands. This will be exploited in a future issue. In a future
# issue should be implemented also a subband weighting procedure in
# order to sent first the most energetic coeffs. Notice, however, that
# these subband weights depends on the selected wavelet.
#

import sounddevice as sd
import struct
import numpy as np
import pywt as wt
import math
from intercom import Intercom
from intercom_dfc import Intercom_DFC

if __debug__:
    import sys

class Intercom_DWT(Intercom_DFC):

    def init(self, args):
        Intercom_DFC.init(self, args)
        self.precision_bits = 32
        self.precision_type = np.int32
        self.number_of_bitplanes_to_send = self.precision_bits * self.number_of_channels
        print("{}".format(self.number_of_bitplanes_to_send))
        print("intercom_bitplanes: transmitting by bitplanes")
        self.max_number_of_bitplanes_to_send = self.number_of_bitplanes_to_send
        self.number_of_received_bitplanes = self.max_number_of_bitplanes_to_send 

    def record_send_and_play_stereo(self, indata, outdata, frames, time, status):
        indata[:,1] -= indata[:,0]
        signs = indata & 0x80000000
        magnitudes = abs(indata)
        indata = signs | magnitudes
        self.send(indata)
        chunk = self._buffer[self.played_chunk_number % self.cells_in_buffer]
        signs = chunk >> 31
        magnitudes = chunk & 0x7FFFFFFF
        #chunk = ((~signs & magnitudes) | ((-magnitudes) & signs))
        chunk = magnitudes + magnitudes*signs*2
        self._buffer[self.played_chunk_number % self.cells_in_buffer] = chunk
        self._buffer[self.played_chunk_number % self.cells_in_buffer][:,1] += self._buffer[self.played_chunk_number % self.cells_in_buffer][:,0]
        self.play(outdata)
        self.received_bitplanes_per_chunk[self.played_chunk_number % self.cells_in_buffer] = 0
        #print(*self.received_bitplanes_per_chunk)

    # Runs the intercom and implements the buffer's logic.
    def run(self):
        self.recorded_chunk_number = 0
        self.played_chunk_number = 0
        with sd.Stream(samplerate=self.frames_per_second, blocksize=self.frames_per_chunk, dtype=np.int32, channels=self.number_of_channels, callback=self.record_send_and_play):
            print("intercom_buffer: ¯\_(ツ)_/¯ Press <CTRL> + <c> to quit ¯\_(ツ)_/¯")
            first_received_chunk_number = self.receive_and_buffer()
            self.played_chunk_number = (first_received_chunk_number - self.chunks_to_buffer) % self.cells_in_buffer
            while True:
                self.receive_and_buffer()

    def generate_zero_chunk(self):
        cell = np.zeros((self.frames_per_chunk, self.number_of_channels), np.int32)
        return cell


if __name__ == "__main__":
    intercom = Intercom_DWT()
    parser = intercom.add_args()
    args = parser.parse_args()
    intercom.init(args)
    intercom.run()
