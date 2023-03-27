import glob
import os.path
import sys

from PySide6 import QtCore, QtWidgets
import soundfile as sf
from datetime import timedelta

formatTypes = ['PCM_16', 'PCM_24', 'PCM_32', 'FLOAT', 'DOUBLE']

offsetAndSafeSpace = 100


def to_time(time_str: str):
    h = 0
    m = 0
    s = 0
    f = 0
    res = True
    try:
        split1 = time_str.split(".")
        if len(split1) == 1:
            f = 0
        elif len(split1) == 2:
            f = int(split1[1])
        else:
            res = False
        split2 = split1[0].split(":")
        if len(split2) > 3 or not res:
            res = False
        elif len(split2) == 1:
            s = int(split2[0])
        elif len(split2) == 2:
            s = int(split2[1])
            m = int(split2[0])
        else:
            s = int(split2[2])
            m = int(split2[1])
            h = int(split2[0])
    except ValueError:
        res = False

    return [res, h, m, s, f]


class MyWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.maxchannels = 64

        self.outdir = ""

        self.infiles = []
        self.numChannels = 0
        self.sampleRate = 0
        self.numSamples = 0

        self.setWindowTitle("XWLive Extract")

        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.button_selectInput = QtWidgets.QPushButton("Select Input Directory")
        self.main_layout.addWidget(self.button_selectInput)
        self.button_selectInput.clicked.connect(self.select_input)

        self.label_inputfile = QtWidgets.QLabel("No input directory selected")
        self.main_layout.addWidget(self.label_inputfile)

        self.label_inputinfo = QtWidgets.QLabel("---")
        self.main_layout.addWidget(self.label_inputinfo)

        self.layout_between = QtWidgets.QHBoxLayout()
        self.edit_start = QtWidgets.QLineEdit()
        self.edit_start.setMaximumWidth(150)
        self.edit_start.setText('00:00:00')
        self.layout_between.addWidget(self.edit_start)
        self.label_between1 = QtWidgets.QLabel(" - ")
        self.layout_between.addWidget(self.label_between1)
        self.edit_end = QtWidgets.QLineEdit()
        self.edit_end.setMaximumWidth(150)
        self.edit_end.setText("00:00:00")
        self.layout_between.addWidget(self.edit_end)
        self.label_between2 = QtWidgets.QLabel("Format: hh:mm:ss.samples")
        self.layout_between.addWidget(self.label_between2)
        self.layout_between.addSpacerItem(
            QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        self.main_layout.addLayout(self.layout_between)

        self.scrolllayout = QtWidgets.QVBoxLayout()
        self.channelLabels = []
        self.channelNames = []
        self.horLayouts = []
        self.checkOuts = []
        for i in range(self.maxchannels):
            self.horLayouts.append(QtWidgets.QHBoxLayout())
            self.checkOuts.append(QtWidgets.QCheckBox())
            self.checkOuts[i].setChecked(True)
            self.horLayouts[i].addWidget(self.checkOuts[i])
            self.channelLabels.append(QtWidgets.QLabel("Name Ch. " + str(i + 1) + ":"))
            self.channelLabels[i].setMinimumWidth(100)
            self.horLayouts[i].addWidget(self.channelLabels[i])
            self.channelNames.append(QtWidgets.QLineEdit())
            self.horLayouts[i].addWidget(self.channelNames[i])
            self.horLayouts[i].addSpacerItem(
                QtWidgets.QSpacerItem(40, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
            self.scrolllayout.addLayout(self.horLayouts[i])
        self.scrollwidget = QtWidgets.QWidget()
        self.scrollwidget.setLayout(self.scrolllayout)
        self.scrollchannels = QtWidgets.QScrollArea()
        self.scrollchannels.setWidget(self.scrollwidget)
        self.scrollchannels.setWidgetResizable(True)
        self.main_layout.addWidget(self.scrollchannels)

        self.button_selectOutput = QtWidgets.QPushButton("Select Output Directory")
        self.main_layout.addWidget(self.button_selectOutput)
        self.button_selectOutput.clicked.connect(self.select_output)

        self.label_outputdir = QtWidgets.QLabel("No output directory selected")
        self.main_layout.addWidget(self.label_outputdir)

        self.format_select = QtWidgets.QComboBox()
        self.format_select.addItems(formatTypes)
        self.format_select.setCurrentIndex(1)
        self.label_format = QtWidgets.QLabel("Export format:")
        self.layout_format = QtWidgets.QHBoxLayout()
        self.layout_format.addWidget(self.label_format)
        self.layout_format.addWidget(self.format_select)
        self.layout_format.addSpacerItem(
            QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        self.main_layout.addLayout(self.layout_format)

        self.buttonConvert = QtWidgets.QPushButton("Convert!")
        self.main_layout.addWidget(self.buttonConvert)
        self.buttonConvert.clicked.connect(self.do_convert)

        self.progressbar = QtWidgets.QProgressBar()
        self.progressbar.setValue(0)
        self.main_layout.addWidget(self.progressbar)

        self.main_layout.addSpacerItem(
            QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))

    @QtCore.Slot()
    def select_input(self):
        dirname = QtWidgets.QFileDialog.getExistingDirectory(self, "Open Output Directory",
                                                             "",
                                                             QtWidgets.QFileDialog.ShowDirsOnly
                                                             | QtWidgets.QFileDialog.DontResolveSymlinks)
        if dirname == "":
            return

        file_list = glob.glob(os.path.join(dirname, '*.[Ww][Aa][Vv]'))
        file_list.sort()
        if len(file_list) <= 0:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("No wav-file in the directory!")
            msg_box.exec()
            return

        numSamples = 0
        audiofile = sf.SoundFile(file_list[0], 'r')
        if audiofile.channels > self.maxchannels:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Audio file has to many channels!")
            msg_box.exec()
            audiofile.close()
            return
        audiofile.close()

        numSamples += audiofile.frames
        print(file_list[0] + ': ' + str(audiofile.frames) + ' samples')
        sampleRate = audiofile.samplerate
        numChannels = audiofile.channels

        for i in range(1, len(file_list)):
            audiofile = sf.SoundFile(file_list[i], 'r')
            if (sampleRate != audiofile.samplerate) or (numChannels != audiofile.channels):
                msg_box = QtWidgets.QMessageBox()
                msg_box.setText("Audio files in the directory have different format!")
                msg_box.exec()
                audiofile.close()
                return
            numSamples += audiofile.frames
            print(file_list[i] + ': ' + str(audiofile.frames) + ' samples')
            audiofile.close()

        self.numChannels = numChannels
        self.sampleRate = sampleRate
        self.numSamples = numSamples

        self.label_inputfile.setText(dirname)

        time_seconds = numSamples // sampleRate
        time_plusframes = numSamples % sampleRate

        self.label_inputinfo.setText(str(self.numChannels) + " channels, "
                                     + "{:0>8}".format(str(timedelta(seconds=time_seconds)))
                                     + "(+" + str(time_plusframes) + " frames)" + " at "
                                     + str(self.sampleRate) + "Hz")

        for i in range(self.numChannels):
            self.channelNames[i].setVisible(True)
            self.channelLabels[i].setVisible(True)
            self.checkOuts[i].setVisible(True)

        for i in range(self.numChannels, self.maxchannels):
            self.channelNames[i].setVisible(False)
            self.channelLabels[i].setVisible(False)
            self.checkOuts[i].setVisible(False)

        end_f = numSamples % self.sampleRate
        end_s = (numSamples // self.sampleRate) % 60
        end_m = (numSamples // (self.sampleRate * 60)) % 60
        end_h = numSamples // (self.sampleRate * 60 * 60)

        self.edit_end.setText(str(end_h) + f":{end_m:02d}" + f":{end_s:02d}." + str(end_f))
        self.edit_start.setText("00:00:00")

        self.infiles = file_list

    def select_output(self):
        self.outdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Open Output Directory",
                                                                 "",
                                                                 QtWidgets.QFileDialog.ShowDirsOnly
                                                                 | QtWidgets.QFileDialog.DontResolveSymlinks)
        if self.outdir != "":
            self.label_outputdir.setText(self.outdir)

    def do_convert(self):
        self.buttonConvert.setEnabled(False)

        out_format = self.format_select.currentText()

        [res, h, m, s, f] = to_time(self.edit_start.text())
        if not res:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Start/stop time not correct!")
            msg_box.exec()
            return
        start_frame = h * 60 * 60 * self.sampleRate + m * 60 * self.sampleRate + s * self.sampleRate + f

        [res, h, m, s, f] = to_time(self.edit_end.text())
        if not res:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Start/stop time not correct!")
            msg_box.exec()
            return
        end_frame = h * 60 * 60 * self.sampleRate + m * 60 * self.sampleRate + s * self.sampleRate + f

        out_selected = []
        for i in range(self.numChannels):
            if self.checkOuts[i].isChecked():
                out_selected.append(True)
            else:
                out_selected.append(False)

        outfiles = []
        base_names = []
        for i in range(self.numChannels):
            if not out_selected[i]:
                outfiles.append(None)
                continue
            name = self.channelNames[i].text()
            if name != "":
                name = 'ch' + str(i + 1) + "_" + name
            else:
                name = 'ch' + str(i + 1)
            name = os.path.join(self.outdir, name)
            filename = name + ".wav"
            base_names.append(name)
            outfiles.append(sf.SoundFile(filename, 'w', self.sampleRate, 1, out_format))

        self.progressbar.setValue(0)
        QtWidgets.QApplication.processEvents()

        samples_done = 0
        step_len = 10000

        bytes_per_sample = 3 # PCM_24 as standard
        if out_format == "PCM_16":
            bytes_per_sample = 2
        if out_format == "PCM_32":
            bytes_per_sample = 4
        if out_format == "FLOAT":
            bytes_per_sample = 4
        if out_format == "DOUBLE":
            bytes_per_sample = 8

        single_file_frames = 4*1024*1024*1024 // bytes_per_sample
        single_file_blocks = single_file_frames // step_len

        file_block_counter = 0
        file_counter = 0

        done_done = False
        for infilename in self.infiles:
            infile = sf.SoundFile(infilename, "r")
            if (start_frame - samples_done) >= infile.frames:
                samples_done += infile.frames
                infile.close()
                continue
            done = False

            while not done:
                if (start_frame - samples_done) > 0:
                    infile.seek(start_frame - samples_done)
                    samples_done = start_frame
                read_len = step_len
                if (end_frame - samples_done) < step_len:
                    read_len = end_frame - samples_done
                    done_done = True
                data = infile.read(read_len)

                if file_block_counter >= single_file_blocks:
                    file_block_counter = 0
                    file_counter += 1
                    for i in range(self.numChannels):
                        if out_selected[i]:
                            outfiles[i].close()
                            filename = base_names[i] + "-" + str(file_counter) + ".wav"
                            outfiles[i] = sf.SoundFile(filename, 'w', self.sampleRate, 1, out_format)
                file_block_counter += 1

                if self.numChannels == 1:
                    if out_selected[0]:
                        outfiles[0].write(data)
                else:
                    for i in range(self.numChannels):
                        if out_selected[i]:
                            outfiles[i].write(data[:, i])
                samples_done = samples_done + len(data)
                if len(data) < step_len:
                    done = True
                self.progressbar.setValue(100 * samples_done / self.numSamples)
                QtWidgets.QApplication.processEvents()
            infile.close()
            if done_done:
                break

        self.progressbar.setValue(100)

        for i in range(self.numChannels):
            if out_selected[i]:
                outfiles[i].close()

        self.buttonConvert.setEnabled(True)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    widget = MyWidget()
    widget.resize(600, 800)
    widget.show()

    sys.exit(app.exec())
