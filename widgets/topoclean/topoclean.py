'''
Created on 1 mai 2021

@author: CNRA, arxit
'''

from builtins import object
import os

from qgis.core import *
import qgis.utils
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtCore import QCoreApplication
import ZOALuxembourg.main

class TopoClean(object):
    '''
    Main class for the snapping widget
    '''

    def __init__(self, action):
        '''
        Constructor
        '''
        self.topoclean_action=action

    def run(self):
        '''
        Runs the widget
        '''

        project = ZOALuxembourg.main.current_project

        if not project.isZOAProject():
            return

        self.topoclean_action.trigger()

        # Zoom to selected onclick button
        modification_zoa_layer=project.getModificationZOALayer()

        if modification_zoa_layer is not None:
            # Map layers in the TOC
            maplayers = QgsProject.instance().mapLayers()

            # Selection by intersection with 'ZOA MODIFICATION' layer
            for k,layer in list(maplayers.items()):
                if layer.type() != QgsMapLayer.VectorLayer or not ZOALuxembourg.main.current_project.isZOALayer(layer):
                    continue

                areas = []
                for ZOA_feature in modification_zoa_layer.selectedFeatures():
                    cands = layer.getFeatures()
                    for layer_features in cands:
                        if ZOA_feature.geometry().intersects(layer_features.geometry()):
                            areas.append(layer_features.id())

                layer.select(areas)

            entity_count = modification_zoa_layer.selectedFeatureCount()
            canvas = qgis.utils.iface.mapCanvas()
            canvas.zoomToSelected(modification_zoa_layer)
            if entity_count==1:

                ZOALuxembourg.main.qgis_interface.messageBar().clearWidgets()
                ZOALuxembourg.main.qgis_interface.messageBar().pushMessage(QCoreApplication.translate('TopoClean','Information'),
                                                                   QCoreApplication.translate('TopoClean','There is 1 selected entity in ZOA MODIFICATION layer. You can now check geometries'))
            elif entity_count==0:
                ZOALuxembourg.main.qgis_interface.messageBar().pushMessage(QCoreApplication.translate('TopoClean','Information'),
                                                                   QCoreApplication.translate('TopoClean','There is no selected entity in ZOA MODIFICATION layer. You can now check geometries'))
            else:
                qgis.utils.iface.messageBar().pushMessage(QCoreApplication.translate('TopoClean', 'Information'),
                                                                   QCoreApplication.translate('TopoClean','There are {} selected entities in ZOA MODIFICATION layer. You can now check geometries').format(entity_count))
        else :
            qgis.utils.iface.messageBar().pushMessage("Error", "ZOA MODIFICATION layer is not correct")