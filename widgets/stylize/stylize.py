'''
Created on 1 mai 2021

@author: CNRA, arxit
'''

from builtins import object
import os

from qgis.core import *
from qgis.PyQt.QtCore import QCoreApplication

import ZOALuxembourg.main

class StylizeProject(object):
    '''
    Main class for the layers stylize widget
    '''


    def __init__(self):
        '''
        Constructor
        '''
        pass

    def run(self):
        '''
        Runs the widget
        '''

        project = ZOALuxembourg.main.current_project

        if not project.isZOAProject():
            return

        # Map layers in the TOC
        maplayers = QgsProject.instance().mapLayers()

        # Iterates through XSD types
        for type in ZOALuxembourg.main.xsd_schema.types:
            if type.geometry_type is None:
                continue

            uri = project.getTypeUri(type)
            found = False

            # Check whether a layer with type data source exists in the map
            for k,v in list(maplayers.items()):
                if project.compareURIs(v.source(), uri):
                    found = True
                    layer = v
                    break

            if not found:
                continue

            self.stylizeLayer(layer, type)

        ZOALuxembourg.main.qgis_interface.messageBar().pushSuccess(QCoreApplication.translate('StylizeProject','Success'),
                                                                   QCoreApplication.translate('StylizeProject','The layers styling is finished.'))

    def stylizeLayer(self, layer, type):
        '''
        Stylize the current layer

        :param layer: The layer to update
        :type layer: QgsVectorLayer

        :param type: XSD schema type
        :type type: ZOAType
        '''

        qml = os.path.join(ZOALuxembourg.main.plugin_dir,
                               'styles',
                               '{}.qml'.format(type.name))

        layer.loadNamedStyle(qml)