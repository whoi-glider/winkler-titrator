from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5.QtWidgets import QMainWindow

import sys
import os
import logging
from time import strftime,gmtime
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog,QMessageBox
from PyQt5.QtCore import QThread,pyqtSignal
import serial.tools.list_ports
import winkler
from model import serialDevices as sd
from model import iomod
from model import titration as ti
import numpy as np
import config as CONFIG


Mthios = 0.200
root_dir = os.path.join(os.path.expanduser('~'),'winkler-titrator')
logging.basicConfig(filename=os.path.join(root_dir,'log'+strftime("%Y%m%d", \
    gmtime())),level='INFO',format='%(levelname)s %(asctime)s %(message)s')
logging.info('Im logging!')

class runTitration(QThread):

    sig_done = pyqtSignal(bool)

    def __init__(self, titration, guess):
        """
        Make a new thread instance to run a titation without locking gui
        """
        QThread.__init__(self)
        self.current_titration = titration
        self.guess = np.float(guess)


    def __del__(self):
        self.wait()

    def run(self):
        """
        start a titration (triggered by click of pushButton_titrate)
        """
        self.current_titration.titrate(self.guess)
        self.sig_done.emit(True)

class chartUpdater(QThread):

    sig_chart = pyqtSignal()
    sig_cumvol = pyqtSignal(int)

    def __init__(self, fpath):
        """
        loads latest titration data from file and send to plot
        """
        QThread.__init__(self)
        self.filename = fpath
        self.filesize = os.path.getsize(self.filename)
        self.sig_chart.connect
        self.sig_cumvol.connect


    def __del__(self):
        self.wait()

    def run(self):
        """
        start a titration (triggered by click of pushButton_titrate)
        """
        while True:
            if os.path.getsize(self.filename) > self.filesize:
                self.filesize = os.path.getsize(self.filename)
                self.sig_chart.emit()


class AppWindow(QMainWindow,winkler.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        #self.ui.widget_MPL.addWidget(self.canvas)
        self.pushButton_connect.clicked.connect(self.connect)
        self.pushButton_reload.clicked.connect(self.load_ports)
        self.pushButton_flask.clicked.connect(self.flask_clicked)
        self.pushButton_titrate.clicked.connect(self.titrate_clicked)
        #self.comboBox_meter.activated.connect(self.load_ports)
        #self.comboBox_pump.activated.connect(self.load_ports)
        # Connect dispense buttons
        self.pushButton_1uL.clicked.connect(self.dispense_1uL)
        self.pushButton_10uL.clicked.connect(self.dispense_10uL)
        self.pushButton_100uL.clicked.connect(self.dispense_100uL)
        self.pushButton_1000uL.clicked.connect(self.dispense_1000uL)
        self.pushButton_5000uL.clicked.connect(self.dispense_5000uL)
        self.pushButton_customvol.clicked.connect(self.dispense_custom)

        self.checkBox_gran.stateChanged.connect(self.plot_data)
        self.checkBox_zoom.stateChanged.connect(self.plot_data)

        self.load_ports()


    def plot_data(self):

        self.widget_MPL.canvas.ax.cla()
        self.widget_MPL.canvas.ax.grid()
        self.widget_MPL.canvas.ax.set_xlabel('uL')

        if hasattr(self,'titr'):
            if self.checkBox_zoom.isChecked():
                d = np.where(np.abs(self.titr.uL-self.titr.v_end) < 30)
            else:
                d = range(len(self.titr.uL))
            if self.checkBox_gran.isChecked():
                y = self.titr.gF
                self.widget_MPL.canvas.ax.set_ylabel('gran factor')
            else:
                y = self.titr.mV
                self.widget_MPL.canvas.ax.set_ylabel('mV')

            self.widget_MPL.canvas.ax.plot(self.titr.uL[d],y[d],'.-')
            self.widget_MPL.canvas.ax.plot(self.titr.uL[-1],y[-1],'ro')
            self.widget_MPL.canvas.draw()
            self.lcdNumber_dispensed.display(self.titr.cumvol)
            self.lcdNumber_endpoint.display(self.titr.v_end)


    def connect(self):
        #if not (hasattr(self,'pump') and hasattr(self,'meter')):
        #    self.load_ports()
        #print(self.comboBox_meter.currentText())
        #print(self.comboBox_pump.currentText())
        logging.info('connecting serial devices')
        try:
            self.meter = sd.meter(self.comboBox_meter.currentText(),CONFIG.mVpos,CONFIG.Tpos)
            logging.info('meter connected on ' + self.comboBox_meter.currentText())
        except Exception as ex:
            logging.warning(ex)
            QMessageBox.warning(self,'Connect Warning',\
                                'Meter connection failed',QMessageBox.Ok)
        try:
            print ('connecting ' + CONFIG.PUMP_CTRL)
            if CONFIG.PUMP_CTRL == 'MFORCE':
                self.pump = sd.mforce_pump(self.comboBox_pump.currentText())
                logging.info('MFORCE pump connected on ' + self.comboBox_pump.currentText())
            elif CONFIG.PUMP_CTRL == 'MLYNX':
                self.pump = sd.mlynx_pump(self.comboBox_pump.currentText())
                logging.info('MLYNX pump connected on ' + self.comboBox_pump.currentText())

        except:
            QMessageBox.warning(self,'Connect Warning',\
                                'Pump connection failed',QMessageBox.Ok)
            logging.warning('Pump connection failed')


    def flask_clicked(self):
        filename = QFileDialog.getOpenFileName(None,'Test Dialog')
        logging.info('bottle file '+filename[0]+ ' loaded')
        self.botdict = iomod.import_flasks(filename[0])
        botid = sorted(self.botdict.keys())
        for bot in botid:
            self.comboBox_flasks.addItem(bot)
        return filename

    def load_ports(self):
        self.comboBox_meter.clear()
        self.comboBox_pump.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if True:#if 'usb' in p.device or 'COM' in p.device:
                self.comboBox_meter.addItem(p.device)
                self.comboBox_pump.addItem(p.device)

    def titrate_clicked(self):
        guess = float(self.spinBox_guess.value())
        self.lcdNumber_endpoint.display(0)
        self.lcdNumber_dispensed.display(0)
        logging.info('titration started with initial guess '+ str(guess))
        #print('initial guess is ' + str(guess))
        flaskid = self.comboBox_flasks.currentText()
        flaskvol = self.botdict[flaskid]
        logging.info('flask ' + flaskid + ' with volume = ' + str(flaskvol))
        #print('flask volume =' + str(flaskvol))
        if self.checkBox_rapid.isChecked():
            timode = 'rapid'
        else:
            timode = 'normal'
        #print(flaskvol.type())
        self.titr = ti.titration(self.meter,self.pump,flaskid,flaskvol,0.2,\
                            mode=timode)
        self.ti_thr = runTitration(self.titr,guess)
        self.ti_thr.start()
        self.plt_thr = chartUpdater(self.titr.current_file)
        self.plt_thr.sig_chart.connect(self.plot_data)
        #self.plt_thr.sig_cumvol.connect(self.lcdNumber_dispensed.value)
        self.plt_thr.start()
        self.ti_thr.finished.connect(self.titration_done)

    def titration_done(self):
        QMessageBox.warning(self,'','titration complete: endpoint=' +  \
                str(self.titr.endpoint),QMessageBox.Ok)

    def dispense_vol(self,vol):
        try:
            #print('dispensing ' + str(vol) + ' uL')
            self.pump.movr(str(vol))
            logging.info('dispensed  '+str(vol) + ' uL')
        except Exception as ex:
            print(ex)
            QMessageBox.warning(self,'','dispense ' + str(vol) + ' failed', \
                                QMessageBox.Ok)
    def dispense_1uL(self):
        self.dispense_vol(1)
    def dispense_10uL(self):
        self.dispense_vol(10)
    def dispense_100uL(self):
        self.dispense_vol(100)
    def dispense_1000uL(self):
        self.dispense_vol(1000)
    def dispense_5000uL(self):
        self.dispense_vol(5000)
    def dispense_custom(self):
        vol = self.lcdNumber_customvol.value
        self.dispense_vol(vol)


def getPorts():
    ports = serial.tools.list_ports.comports()
    if not ports:
        return ("No Serial Port Detected",'This is not a port')
    else:
        return ports

if __name__ == '__main__':
    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext
    app = QApplication(sys.argv)
    MainWindow = QMainWindow()
    prog = AppWindow()
    prog.show()
    exit_code = appctxt.app.exec_()      # 2. Invoke appctxt.app.exec_()
    sys.exit(exit_code)
