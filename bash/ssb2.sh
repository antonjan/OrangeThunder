#!/bin/sh
#*-----------------------------------------------------------------*
#* ssb.sh
#* Experimental SSB generator chain for FT8 transceiver
#*
#* ssb.sh FREQ [in Hz]
#*-----------------------------------------------------------------*
cat sampleaudio.wav | csdr convert_i16_f \
  | csdr fir_interpolate_cc 2 | csdr dsb_fc \
  | csdr bandpass_fir_fft_cc 0.002 0.06 0.01 | csdr fastagc_ff \
  | sudo /home/pi/rpitx/sendiq -i /dev/stdin -s 96000 -f "$1" -t float

