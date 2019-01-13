#!/usr/bin/python3
#*--------------------------------------------------------------------------
#* wsprRxTx
#*
#* Raspberry Pi based WSPR Rx/Tx configuration
#*
#* Send a WSPR frame and receive  WSPR the rest of the time
#* Based on the  packages
#*     WsprryPi (https://github.com/JamesP6000/WsprryPi)
#*     wsprd    (https://github.com/Guenael/rtlsdr-wsprd)
#* Plus some glueing Python code from my own cooking
#*-------------------------------------------------------------------------
#// License:
#//   This program is free software: you can redistribute it and/or modify
#//   it under the terms of the GNU General Public License as published by
#//   the Free Software Foundation, either version 2 of the License, or
#//   (at your option) any later version.
#//
#//   This program is distributed in the hope that it will be useful,
#//   but WITHOUT ANY WARRANTY; without even the implied warranty of
#//   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#//   GNU General Public License for more details.
#//
#//   You should have received a copy of the GNU General Public License
#//   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#// lu7did: initial load
#*
#* Version 1.1
#*    - improved subprocess management
#*    - telemetry
#*    - improved logging
#*    - changed from GPIO 17 to GPIO 27
#*    - better argument management
#*    - added checkpoint
#*    - added status
#*    - added running lock
#*    - Exception handling 
#* LU7DID
#*-------------------------------------------------------------------------
#* import the necessary packages
#*-------------------------------------------------------------------------
import argparse
import RPi.GPIO
import time
import subprocess
import os
import time
import sys
import datetime
import random
import RPi.GPIO as GPIO
import signal
#*--------------------------------------------------------------------------
#* WSPR Band Table
#*--------------------------------------------------------------------------
bands={
     "160m":1800000,
     "80m": 3500000,
     "40m": 7000000,
     "20m":14095600,
     "15m":21000000,
     "10m":28000000,
     "6m" :50000000,
     "2m":144000000
     }
#*-------------------------------------------------------------------------
#* Init global variables
#*-------------------------------------------------------------------------
id='LU7DID'
grid='GF05TE'
band='20m'
pwr='20'
freq=0
tx=True
VERSION='1.1'
PROGRAM="wsprRxTx"
cycle=5
lckFile=("%s.lck") % PROGRAM
logFile=("%s.log") % PROGRAM
tlmFile=("%s.tlm") % PROGRAM
pidFile=("%s.pid") % PROGRAM
myPID=os.getpid()
DEBUGLEVEL=0
#*------------------------------------------------------------------------
#*  Set  GPIO out port for PTT
#*------------------------------------------------------------------------
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(27, GPIO.OUT)
#*------------------------------------------------------------------------
#* setPTT
#* Activate the PTT thru GPIO27
#*------------------------------------------------------------------------
def setPTT(PTT):
    if PTT==False:
       GPIO.output(27, GPIO.LOW)
       log(0,"setPTT: GPIO27->PTT(%s) -- Receiving mode" % PTT)
    else:
       GPIO.output(27, GPIO.HIGH)
       log(0,"setPTT: GPIO27->PTT(%s) -- Transmit mode" % PTT)
#*-------------------------------------------------------------------------
#* getFreq(band)
#* Transform band into frequency
#*-------------------------------------------------------------------------
def getFreq(b):

    return bands.get(b,0)

#*-------------------------------------------------------------------------
#* log(string)
#* print log thru standard output
#*-------------------------------------------------------------------------
def log(d,st):
    if d<=DEBUGLEVEL:
       m=datetime.datetime.now()
       if logFile != '' : 
          with open(logFile, 'a') as f:
               f.write('%s %s\n' % (m,st))
       print('%s %s' % (m,st))
#*----------------------------------------------------------------------------
#* Exception and Termination handler
#*----------------------------------------------------------------------------
def signal_handler(sig, frame):
   log(0,"signal_handler: WSPR Monitor and Beacon is being terminated, clean up completed!")
   log(0,'Turning GPIO(27) low as PTT')
   setPTT(False)

   try:
     log(0,"Process terminated, clean up completed!")
     if os.file.exists(lckFile) == True:
        os.remove(lckFile)
     if os.file.exists(pidFile) == True:
        os.remove(pidFile)
   except:
     log(0,"signal_handler: Process finalized")
   sys.exit(0)
#*-------------------------------------------------------------------------
#* Exception management
#*-------------------------------------------------------------------------
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

#*--------------------------------------------------------------------------
#* doExec()
#* Execute a command and return the result
#*--------------------------------------------------------------------------
def doExec(cmd):
    log(1,"doExec: [cmd] %s" % cmd)
    p = subprocess.Popen(cmd, shell=True, 
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    rc=p.wait()
    st=''
    for line in p.stdout:
        st=st+line.decode("utf-8").replace("\n","")
    return st

#*--------------------------------------------------------------------------
#* doShell()
#* Execute a command as a shell and print to std out and std error
#*--------------------------------------------------------------------------
def doShell(cmd):
    log(1,"doShell: [cmd] %s" % cmd)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (result, error) = p.communicate()
    rc = p.wait()
    log(1,"doShell: [stdout]= %s" % result)
    log(1,"doShell: [stderr]= %s" % error)

    if rc != 0:
        log(0,"Error: failed to execute command: %s" % cmd)
        log(0,error)
    return result.decode("utf-8")

#*--------------------------------------------------------------------------
#* doService()
#* Manages the monitor service
#*--------------------------------------------------------------------------
def doService(freq):

    if args.ntpd == True:
       log(1,'doService: Starting time synchronization')
       #cmd='sudo chronyc -a makestep'
       cmd='sudo /home/pi/ntpd.sync'
       result=doShell(cmd)
       log(0,"doService: TimeSync(%s)" % str(result).replace("\n",""))
 
    while True:
       #*--------------------------*
       #* PTT low (receive)        *
       #*--------------------------*
       setPTT(False)
       #*--------------------------*
       #* Read and log telemetry   *
       #*--------------------------*
       cmd="python /home/pi/WsprryPi/picheck.py -a"
       result=doShell(cmd)
       log(0,"[TL] %s" % str(result).replace("\n",""))
       with open(tlmFile, 'a') as tlm:
          log(1,"writing telemetry to file %s" % tlmFile)
          tlm.write("%s" % result)
       #*--------------------------*
       #* Receive WSPR             *
       #*--------------------------*
       if args.txonly == False:
          if cycle>1:
             n=getRandom(1,cycle)
          else:
             n=cycle
          log(0,"Starting receiver for %d cycles" % n)
          cmd='sudo /home/pi/rtlsdr-wsprd/rtlsdr_wsprd -f %d -c %s -l %s -d 2 -n %d -a 1 -S' % (freq,id,grid,n)
          result=doShell(cmd)       
          log(0,"[RX]\n%s" % result)

       if args.rxonly == False:
       #*--------------------------*
       #* PTT high (transmit)      *
       #*--------------------------*
          setPTT(True)
       #*--------------------------*
       #* Transmit cycle           *
       #*--------------------------*
       #*--- NO USAR log(0,"Starting beacon %s grid=%s pwr=%s band=%s" (id,grid,pwr,band))
          cmd='sudo /home/pi/WsprryPi/wspr -r -o -s -x 1 %s %s %s %s' % (id,grid,pwr,band)
       #*--- NO USAR log(0,"[c]:%s" % cmd)
          result=doShell(cmd)       
          log(0,"[TX]\n%s" % result)

       setPTT(False)

#*--------------------------------------------------------------------------
#* getRandom
#* Return an integer random number between two values [min,max]
#*--------------------------------------------------------------------------
def getRandom(nmin,nmax):
    return random.randint(nmin,nmax)

#*--------------------------------------------------------------------------
#* startService()
#*
#*--------------------------------------------------------------------------
def startService():
    if (id=='') or (grid=='') or (band==''):
       log(0,'Start command required id,grid and band to be set, exit')
       exit() 

    freq=getFreq(band)
    if freq==0 :
       log(0,'Non supported band(%s), exit' % band)
       exit()
    log(1,"Starting daemon PID(%d) and creating PID %s" % (myPID,pidFile))
    #createPID()
    #log(1,"%s PID file created" % pidFile)
    try:
      doService(freq)
    except Exception as e:
      log(0,"Exception detected, program being terminated Exception(%s)" % str(e.message))
      log(0,"Exception detected, %s" % repr(e))
    else:
      log(0,"Program is ending normally")


#*--------------------------------------------------------------------------
#* isRunning
#* Explore if another instance of the daemon is running
#*--------------------------------------------------------------------------
def isRunning():
    cmd="sudo ps -aux | pgrep \"%s\" " % PROGRAM
    log(1,"doExec: [cmd] %s" % cmd)
    p = subprocess.Popen(cmd, shell=True, 
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    rc=p.wait()
    for line in p.stdout:
        s=line.decode("utf-8").replace("\n","")
        log(2,"PID(%s)" % s)
        if int(s)!=int(myPID):
           log(2,"Detected PID(%s) as a running instance" % s)
           return s
    return ""

#*============================================================================
#* Main Program
#*
#*============================================================================

#*---------------------------------------------------------------------------
# construct the argument parse and parse the arguments
#*---------------------------------------------------------------------------

ap = argparse.ArgumentParser()

#*--- Add all defined arguments

ap.add_argument("--start", help="Start the WSPR Transceiver", required=False, action="store_true")
ap.add_argument("--stop",help="Stop the WSPR Transceiver",required=False, action="store_true")
ap.add_argument("--list",help="List the WSPR Transceiver", required=False, action="store_true")
ap.add_argument("--id",help="Callsign to be used",required=False)
ap.add_argument("--grid",help="QTH Locator",required=False)
ap.add_argument("--band",help="Band to use i.e. 20m",required=False)
ap.add_argument("--pwr",help="Set Power in dBm",required=False)
ap.add_argument("--tx",help="Enable TX",required=False, action="store_true")
ap.add_argument("--cycle",help="Cycles RX/TX",required=False)
ap.add_argument("--log",help="Log activity to file",default=True,required=False,action="store_true")
ap.add_argument("--lock",help="Lock further execution till reset",required=False,action="store_true")
ap.add_argument("--reset",help="Reset locked execution", required=False,action="store_true")
ap.add_argument("--debug",help="Debug level", required=False,default=0)
ap.add_argument("--force",help="Force start", required=False,default=False,action="store_true")
ap.add_argument("--ntpd",help="Force ntpd sync", required=False,default=False,action="store_true")
ap.add_argument("--rxonly",help="Force only receiving", required=False,default=False,action="store_true")
ap.add_argument("--txonly",help="Force ntpd transmitting", required=False,default=False,action="store_true")

args=ap.parse_args()

#*---------------------------*
#* Process log command       *
#*---------------------------*

if args.log == True :
   logFile="%s.log" % PROGRAM
   with open(logFile, 'w+') as f:
      f.write("")
   log(2,'(log) Set logfile(%s)' % logFile)

log(0,"Program %s Version %s PID(%d)" % (PROGRAM,VERSION,os.getpid()))
#*---------------------------*
#* Process receive only      *
#*---------------------------*

if args.rxonly == True:
   log(0,"(rxonly) Receiving only mode activated")
#*---------------------------*
#* Process transmit only     *
#*---------------------------*

if args.txonly == True:
   log(0,"(txonly) Transmit only mode activated")

#*---------------------------*
#* Process debug level       *
#*---------------------------*

if int(args.debug) != 0:
   DEBUGLEVEL=int(args.debug)
   log(0,"(debug) Debug level set to %d" % DEBUGLEVEL)

#*---------------------------*
#* Process force command     *
#*---------------------------*

if args.force == True:

   pid=isRunning()
   if(pid == ''):
      log(0,'(force) Daemon is not running')
   else:
      log(0,'(force) Daemon found PID(%s), killing it' % pid)
      n=int(pid)
      cmd="sudo kill %s" % n
      result=doShell(cmd)
      log(0,'(force) Killing process completed')
   if os.path.isfile(pidFile) == True:
      os.remove(pidFile)   
      log(0,'(force) pidFile %s removed' % pidFile)

#*---------------------------*
#* Process id command        *
#*---------------------------*

if args.id != None :
   id=args.id.upper()
   log(0,'(id) Set Callsign id(%s)' % id)

#*---------------------------*
#* Process cycle command     *
#*---------------------------*

if args.cycle != None:
   cycle=int(args.cycle)
   log(0,'(cycle) Set RX/TX cycle (%d)' % cycle)

#*---------------------------*
#* Process grid  command     *
#*---------------------------*

if args.grid != None :
   grid=args.grid.upper()
   log(0,'(grid) Set maiden QTH Locator grid(%s)' % grid)

#*---------------------------*
#* Process band command      *
#*---------------------------*

if args.band != None :
   band=args.band.upper()
   log(0,'(band) Set Band(%s)' % band)

#*---------------------------*
#* Process Tx command        *
#*---------------------------*
if args.tx != False :
   tx=args.tx
   log(0,'(tx) Set Tx(%s)' % str(tx))

#*---------------------------*
#* Process Power command     *
#*---------------------------*
if args.pwr != None :
   pwr=args.pwr
   log(0,'(pwr) Set Power(%s)' % pwr)

#*---------------------------*
#* Process start command     *
#*---------------------------*
if args.start:
   PID=isRunning()
   if PID == '':
      setPTT(False)
      startService()
   else:
      log(0,"(start) Daemon already running PID(%s), exit" % PID)
   exit()    
#*---------------------------*
#* Process stop command      *
#*---------------------------*
if args.stop:
   pid=isRunning()
   if(pid == ''):
     log(0,'Daemon is not running, exit')
   else:
     log(0,'Daemon found PID(%s)' % pid)
   exit()
#*----------------------------------------------------------------------------
#* Review lock status
#*----------------------------------------------------------------------------
if args.lock == True:
   exit()

if args.reset == True:
   exit()

#*------------------------------------*
#* Process list command (default)     *
#*------------------------------------*
pid=isRunning()
if (pid == ''):
   log(0,'Status: Daemon is not running, exit')
else:
   log(0,'Status: Daemon is running PID(%s)' % (pid))
exit()
#*--------------------------------[End of program] -----------------------------------------------