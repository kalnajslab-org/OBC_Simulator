# OBC Simulator

This repository contains a platform-independent, Python-based simulator for the Zephyr Onboard Computer (OBC) for the CNES Strateole 2 campaign. This simulator adds the ability to receive and display debug messages from LASP instruments over the same serial connection as the XML-based OBC communications.

## Interface

The simulator uses the `PySimpleGUI` library to provide multiple input and output windows that allow the user to interact with the instrument under test.

### Startup

On startup, the user has the following options:

![Welcome Window Screenshot](/Screenshots/WelcomeWindow.PNG)

Example ports: (Windows) `COM3`, (Linux/MacOS) `/dev/tty.usbserial`

If the user responds "Yes" to the "Automatically respond with ACKs?" prompt, then in response to `S`, `RA`, and `TM` XML messages, the simulator will send affirmative `SAck`, `RAAck`, and `TMAck` messages respectively. This is the default option. Otherwise, the user must manually send these commands.

### Sending Commands

![Command Menu Screenshot](/Screenshots/CommandMenu.PNG)

### Simulator Log

![Debug Window Screenshot](/Screenshots/DebugWindow.PNG)

### Viewing Instrument Output

![Instrument Output Screenshot](/Screenshots/InstrumentOutput.PNG)

## Log File Structure

Each time an OBC Simulator session is successfully started, a directory under the `sessions/` directory is created. Each session's directory will be named according to the date and instrument: `INST_DD-Mmm-YY_HH-MM-SS/`.

### Session Contents

`INST_CMD_DD-Mmm-YY_HH-MM-SS.txt`: logs all of the commands sent to the instrument

`INST_DBG_DD-Mmm-YY_HH-MM-SS.txt`: logs all of the debug messages received from the instrument

`INST_XML_DD-Mmm-YY_HH-MM-SS.txt`: logs all of the XML messages received from the instrument

`TM`: directory containing individual, timestamped files for each telemetry message in the same format as found on the CCMZ

### Example File Structure

```
sessions/
|---RACHUTS_04-Jun-20_12-04-32/
|   |   RACHUTS_CMD_04-Jun-20_12-04-32.txt
|   |   RACHUTS_DBG_04-Jun-20_12-04-32.txt
|   |   RACHUTS_XML_04-Jun-20_12-04-32.txt
|   |---TM/
|       |    TM_04-Jun-20_12-04-37.RACHUTS.dat
|       |    TM_04-Jun-20_12-04-43.RACHUTS.dat
|---LPC_05-Jun-20_13-07-32/
|   |   LPC_CMD_05-Jun-20_13-07-32.txt
|   |   LPC_DBG_05-Jun-20_13-07-32.txt
|   |   LPC_XML_05-Jun-20_13-07-32.txt
|   |---TM/
|       |    TM_05-Jun-20_13-07-37.LPC.dat
|       |    TM_05-Jun-20_13-07-43.LPC.dat
|---etc...
```

## Scripting

The `Legacy/` directory contains old scripts used to run the original simulator code. The advantage of using scripting is automation. **In the future, this could be achieved with the new architecture by writing out a list of commands with along with timing in a file to be parsed and sent**.