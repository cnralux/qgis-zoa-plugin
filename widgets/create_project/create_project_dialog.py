# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CreateProjectDialog
                                 A QGIS plugin
 Gestion de la ZOA du Grand-Duché de Luxembourg
                             -------------------
        begin                : 2021-05-01
        copyright            : (C) 2015 by arx iT
        edit                 : 2021 by CNRA
        email                : ta-upload@cnra.etat.lu
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from qgis.PyQt import QtGui, uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.PyQt.QtCore import QCoreApplication

import ZOALuxembourg.main

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'create_project_dialog.ui'))


class CreateProjectDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        '''
        Constructor.
        '''

        super(CreateProjectDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

    def showFolderList(self):
        '''
        Display the project folder selection dialog
        '''

        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly)
        dialog.setWindowTitle(QCoreApplication.translate('CreateProject','Select the new project location'))
        dialog.setSizeGripEnabled(False)
        result = dialog.exec_()

        if result == 0:
            return

        selected_files = dialog.selectedFiles()

        if len(selected_files)==0:
            return

        self.txtProjectFolder.setText(selected_files[0])

    def clear(self):
        '''
        Clears the text boxes
        '''

        self.txtProjectName.setText('')
        self.txtProjectFolder.setText('')

    def accept(self):
        '''
        Dialog accept action (OK)
        '''

        folder = self.txtProjectFolder.text()
        name = self.txtProjectName.text()

        # No project name
        if len(name)==0:
            QMessageBox.critical(self,
                                 QCoreApplication.translate('CreateProject','Error'),
                                 QCoreApplication.translate('CreateProject','Please type a project name'))

        # Project folder error
        if not os.path.exists(folder):
            QMessageBox.critical(self,
                                 QCoreApplication.translate('CreateProject','Error'),
                                 QCoreApplication.translate('CreateProject','The folder does not exist'))

        ZOALuxembourg.main.current_project.create(folder,name)

        self.close()