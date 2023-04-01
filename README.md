What is XWLive Extractor?
------------
**XWLive Extractor** is a simple Python script that is meant to convert single channel audio files from multichannel audio recording files as they are created by XLive (Behringer X32, Midas M32) or WLive (Behringer Wing) cards.  

How it works:
- Select the input directory containing the multichannel wave files from your recording.
- Select an output directory where you want to store the single channel wave files. (Be aware that existing files might be overwritten without asking!)
- Click on convert.
- Wait until the progress bar reaches 100%. You're done.

Furthermore you can
- give the channels names. Then the file names will contain these names.
- select which channel you want to have exported. By default all channels will be exported.
- limit the time range to export.
- choose the export format.
- links output channels. "Linked" channels will be included in the file from the channel above. You can link an arbitrary number of channels to one file.

Requirements:
- Pyside6
- soundfile

You can install them by typing 
> pip install pyside6

> pip install soundfile

Export formats are:
- PCM_16 : 16 bit signed integer
- PCM_24 : 24 bit signed integer (default)
- PCM_32 : 32 bit signed integer	
- FLOAT : 32 bit floating point
- DOUBLE : 64 bit floating point


License
-------
XWLive Extractor is licensed under the terms
of the GNU General Public License, version 3. A copy of the license
can be found in the file LICENSE which can be found in the source
archive. You can read it here: http://www.gnu.org/licenses/gpl-3.0.html





