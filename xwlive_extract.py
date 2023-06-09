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


def se_log_extract(bytecode: bytes):
    # Format of the file was figured out with the help of the code at https://github.com/pmaillot/X32-Behringer
    name_bytes = bytecode[1552:1572]
    split_pos = 0
    while split_pos < 19:
        if name_bytes[split_pos] == 0:
            break
        split_pos += 1
    if split_pos == 0:
        name = ''
    else:
        name_bytes = name_bytes[0:split_pos]
        name = name_bytes.decode("utf-8")
    position = 1052
    vals = []
    while position < 1552:
        val = (bytecode[position]) + (bytecode[position + 1] << 8) \
              + (bytecode[position + 2] << 16) + (bytecode[position + 3] << 24)
        if val != 0:
            vals.append(val)
        else:
            break
        position += 4
    time_code = (bytecode[0]) + (bytecode[1] << 8) + (bytecode[2] << 16) + (bytecode[3] << 24)
    time_year = (time_code >> 25) + 1980
    time_month = ((time_code & 0x1FFFFFF) >> 21)
    time_day = ((time_code & 0x1FFFFF) >> 16)
    time_hour = ((time_code & 0xFFFF) >> 11)
    time_minute = ((time_code & 0x7FF) >> 5)
    time_second = ((time_code & 0x1F) * 2)
    time_str = f"{time_day:02d}.{time_month:02d}.{time_year} {time_hour:02d}:{time_minute:02d}:{time_second:02d}"

    return [name, vals, time_str]


def samples_to_time_string(samples, fs):
    f = samples % fs
    s = (samples // fs) % 60
    m = (samples // (fs * 60)) % 60
    h = samples // (fs * 60 * 60)
    if f == 0:
        return str(h) + f":{m:02d}" + f":{s:02d}"
    else:
        return str(h) + f":{m:02d}" + f":{s:02d}." + str(f)


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
        self.edit_start = QtWidgets.QComboBox()
        self.edit_start.setEditable(True)
        self.edit_start.setMinimumWidth(200)
        self.edit_start.setCurrentText('00:00:00')
        self.layout_between.addWidget(self.edit_start)
        self.label_between1 = QtWidgets.QLabel(" - ")
        self.layout_between.addWidget(self.label_between1)
        self.edit_end = QtWidgets.QComboBox()
        self.edit_end.setEditable(True)
        self.edit_end.setMinimumWidth(200)
        self.edit_end.setCurrentText("00:00:00")
        self.layout_between.addWidget(self.edit_end)
        self.label_between2 = QtWidgets.QLabel("Format: hh:mm:ss.samples")
        self.layout_between.addWidget(self.label_between2)
        self.layout_between.addSpacerItem(
            QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        self.main_layout.addLayout(self.layout_between)

        self.layout_select = QtWidgets.QHBoxLayout()
        self.button_select_all = QtWidgets.QPushButton("Select All")
        self.button_select_all.clicked.connect(self.select_all)
        self.layout_select.addWidget(self.button_select_all)
        self.button_select_none = QtWidgets.QPushButton("Select None")
        self.button_select_none.clicked.connect(self.select_none)
        self.layout_select.addWidget(self.button_select_none)
        self.layout_select.addSpacerItem(
            QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
        self.main_layout.addLayout(self.layout_select)

        self.scrolllayout = QtWidgets.QVBoxLayout()
        self.channelLabels = []
        self.channelNames = []
        self.horLayouts = []
        self.checkOuts = []
        self.checkLinks = []
        self.channelLabelNames = []
        self.channelLines = []
        for i in range(self.maxchannels):
            self.horLayouts.append(QtWidgets.QHBoxLayout())
            self.channelLabels.append(QtWidgets.QLabel("Ch. " + str(i + 1) + " "))
            self.channelLabels[i].setMinimumWidth(50)
            self.horLayouts[i].addWidget(self.channelLabels[i])
            self.checkOuts.append(QtWidgets.QCheckBox())
            self.checkOuts[i].setChecked(True)
            self.checkOuts[i].setText("Export")
            self.horLayouts[i].addWidget(self.checkOuts[i])
            self.checkLinks.append(QtWidgets.QCheckBox())
            self.checkLinks[i].setChecked(False)
            self.checkLinks[i].setText("Link")
            self.checkLinks[i].stateChanged.connect(self.update_ui_channels)
            self.horLayouts[i].addWidget(self.checkLinks[i])
            self.channelLabelNames.append(QtWidgets.QLabel("Name: "))
            self.channelLabelNames[i].setMinimumWidth(60)
            self.horLayouts[i].addWidget(self.channelLabelNames[i])
            self.channelNames.append(QtWidgets.QLineEdit())
            self.horLayouts[i].addWidget(self.channelNames[i])
            self.horLayouts[i].addSpacerItem(
                QtWidgets.QSpacerItem(40, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
            self.scrolllayout.addLayout(self.horLayouts[i])
            self.channelLines.append(QtWidgets.QFrame())
            self.channelLines[i].setFrameShape(QtWidgets.QFrame.Shape.HLine)
            self.channelLines[i].setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
            self.scrolllayout.addWidget(self.channelLines[i])
        self.channelLines[self.maxchannels - 1].setVisible(False)
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

        for i in range(self.numChannels):
            self.channelNames[i].setVisible(True)
            self.channelLabels[i].setVisible(True)
            self.checkOuts[i].setVisible(True)
            self.channelLines[i].setVisible(True)
            self.channelLabelNames[i].setVisible(True)
            self.checkLinks[i].setVisible(True)

        for i in range(self.numChannels, self.maxchannels):
            self.channelNames[i].setVisible(False)
            self.channelLabels[i].setVisible(False)
            self.checkOuts[i].setVisible(False)
            self.channelLines[i].setVisible(False)
            self.channelLabelNames[i].setVisible(False)
            self.checkLinks[i].setVisible(False)

        self.channelLines[self.numChannels - 1].setVisible(False)

        self.infiles = file_list

        logfile_name = os.path.join(dirname, 'SE_LOG.BIN')
        name = ""
        if os.path.isfile(logfile_name):
            with open(logfile_name, mode="rb") as logfile:
                [name, markers, create_time] = se_log_extract(logfile.read())
                print(name)
                print(create_time)
                print(markers)

        input_info_text = create_time + ":   "
        if name != "":
            input_info_text = name + " (" + create_time + "):   "

        input_info_text += str(self.numChannels) + " channels, " \
                           + "{:0>8}".format(str(timedelta(seconds=time_seconds))) \
                           + "(+" + str(time_plusframes) + " frames)" + " at " \
                           + str(self.sampleRate) + "Hz"

        self.label_inputinfo.setText(input_info_text)

        self.edit_start.clear()
        self.edit_end.clear()

        self.edit_start.addItem("(Start) 0:00:00")
        self.edit_end.addItem("(Start) 0:00:00")

        i = 0
        for marker in markers:
            i += 1
            self.edit_start.addItem('(M' + str(i) + ') ' + samples_to_time_string(marker, self.sampleRate))
            self.edit_end.addItem('(M' + str(i) + ') ' + samples_to_time_string(marker, self.sampleRate))

        self.edit_start.addItem('(End) ' + samples_to_time_string(numSamples, self.sampleRate))
        self.edit_end.addItem('(End) ' + samples_to_time_string(numSamples, self.sampleRate))

        self.edit_end.setCurrentText(samples_to_time_string(numSamples, self.sampleRate))
        self.edit_start.setCurrentText("00:00:00")

    def select_all(self):
        for i in range(self.maxchannels):
            self.checkOuts[i].setChecked(True)

    def select_none(self):
        for i in range(self.maxchannels):
            self.checkOuts[i].setChecked(False)

    def select_output(self):
        self.outdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Open Output Directory",
                                                                 "",
                                                                 QtWidgets.QFileDialog.ShowDirsOnly
                                                                 | QtWidgets.QFileDialog.DontResolveSymlinks)
        if self.outdir != "":
            self.label_outputdir.setText(self.outdir)

    def update_ui_channels(self):
        for i in range(1, self.maxchannels):
            if self.checkLinks[i].isChecked():
                self.checkOuts[i].setEnabled(False)
                self.channelNames[i].setEnabled(False)
            else:
                self.checkOuts[i].setEnabled(True)
                self.channelNames[i].setEnabled(True)

    def do_convert(self):
        self.buttonConvert.setEnabled(False)

        out_format = self.format_select.currentText()

        [res, h, m, s, f] = to_time(self.edit_start.currentText().split(')')[-1])
        if not res:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Start/stop time not correct!")
            msg_box.exec()
            self.buttonConvert.setEnabled(True)
            return
        start_frame = h * 60 * 60 * self.sampleRate + m * 60 * self.sampleRate + s * self.sampleRate + f

        [res, h, m, s, f] = to_time(self.edit_end.currentText().split(')')[-1])
        if not res:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Start/stop time not correct!")
            msg_box.exec()
            self.buttonConvert.setEnabled(True)
            return
        end_frame = h * 60 * 60 * self.sampleRate + m * 60 * self.sampleRate + s * self.sampleRate + f

        out_selected = []
        for i in range(self.numChannels):
            if self.checkOuts[i].isChecked():
                out_selected.append(True)
            else:
                out_selected.append(False)

        comb_channels = []
        ch_start = 0
        for i in range(self.numChannels - 1):
            if not self.checkLinks[i + 1].isChecked():
                if self.checkOuts[ch_start].isChecked():
                    comb_channels.append([ch_start, i])
                ch_start = i + 1
        if self.checkOuts[ch_start].isChecked():
            comb_channels.append([ch_start, self.numChannels - 1])

        print("Output channel ranges: ", comb_channels)

        num_outs = len(comb_channels)

        outfiles = []
        base_names = []
        for i in range(num_outs):
            ch_start = comb_channels[i][0]
            ch_end = comb_channels[i][1]
            name = self.channelNames[ch_start].text()
            if name != "":
                name = "_" + name
            if ch_start == ch_end:
                name = 'ch' + str(ch_start + 1) + name
            else:
                name = 'ch' + str(ch_start + 1) + "-" + str(ch_end + 1) + name
            name = os.path.join(self.outdir, name)
            filename = name + ".wav"
            base_names.append(name)
            outfiles.append(sf.SoundFile(filename, 'w', self.sampleRate, ch_end - ch_start + 1, out_format))

        self.progressbar.setValue(0)
        QtWidgets.QApplication.processEvents()

        samples_done = 0
        step_len = 10000

        bytes_per_sample = 3  # PCM_24 as standard
        if out_format == "PCM_16":
            bytes_per_sample = 2
        if out_format == "PCM_32":
            bytes_per_sample = 4
        if out_format == "FLOAT":
            bytes_per_sample = 4
        if out_format == "DOUBLE":
            bytes_per_sample = 8

        single_file_frames = 4 * 1024 * 1024 * 1024 // bytes_per_sample
        single_file_blocks = single_file_frames // step_len

        comb_file_blocks = []
        file_block_counter = []
        file_counter = []
        for i in range(num_outs):
            comb_file_blocks.append(single_file_blocks // (comb_channels[i][1] - comb_channels[i][0] + 1))
            file_block_counter.append(0)
            file_counter.append(0)

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

                for i in range(num_outs):
                    if file_block_counter[i] >= comb_file_blocks[i]:
                        file_block_counter[i] = 0
                        file_counter[i] += 1
                        outfiles[i].close()
                        filename = base_names[i] + "-" + str(file_counter[i]) + ".wav"
                        outfiles[i] = sf.SoundFile(filename, 'w', self.sampleRate,
                                                   comb_channels[i][1] - comb_channels[i][0] + 1, out_format)
                    file_block_counter[i] += 1

                if self.numChannels == 1:
                    if out_selected[0]:
                        outfiles[0].write(data)
                else:
                    for i in range(num_outs):
                        outfiles[i].write(data[:, comb_channels[i][0]:(comb_channels[i][1] + 1)])
                samples_done = samples_done + len(data)
                if len(data) < step_len:
                    done = True
                self.progressbar.setValue(100 * samples_done / self.numSamples)
                QtWidgets.QApplication.processEvents()
            infile.close()
            if done_done:
                break

        self.progressbar.setValue(100)

        for i in range(num_outs):
            outfiles[i].close()

        self.buttonConvert.setEnabled(True)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    widget = MyWidget()
    widget.resize(600, 800)
    widget.show()

    sys.exit(app.exec())
