'''
Created on 1 mai 2021
Edited on 30 august 2022

@author: INRA, arxit
'''
from __future__ import absolute_import

from builtins import str
from builtins import object
import os

import processing
from processing.tools import *

from qgis.core import *
import qgis.utils
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtCore import QCoreApplication

from ZOALuxembourg.schema import *
import ZOALuxembourg.main

from .error_summary_dialog import ErrorSummaryDialog

class DataChecker(object):
    '''
    Main class for the data checker widget
    '''

    def __init__(self):
        '''
        Constructor
        '''

    def run(self):
        '''
        Runs the widget

        :returns: True if there's no errors
        :rtype: Boolean
        '''

        project = ZOALuxembourg.main.current_project

        if not project.isZOAProject():
            return

        layer_structure_errors = list()
        data_errors = list()

        # 'ZOA MODIFICATION' layer definition
        layer_ZOA = project.getModificationZOALayer()

        # 'ZOA MODIFICATION' selection definition
        selection_ZOA = layer_ZOA.selectedFeatures()

        # Counting number entities in 'ZOA MODIFICATION' selection
        entity_count_ZOA = layer_ZOA.selectedFeatureCount()

        # Iterates through XSD types
        for type in ZOALuxembourg.main.xsd_schema.types:
            layer = project.getLayer(type)

            if layer is None:
                continue

            warn_errors, fatal_errors = self.checkLayerStructure(layer, type)
            layer_structure_errors = layer_structure_errors + warn_errors + fatal_errors

            if len(fatal_errors)>0:
                continue

            layer_data_errors = self.checkLayerData(selection_ZOA, layer, type)
            data_errors.append(layer_data_errors)

        # Flatten data errors
        data_errors_flat = list()
        for layer, errors in data_errors:
            for feature, field, message in errors:
                data_errors_flat.append((layer, feature, field, message))

        valid = (len(layer_structure_errors) + len(data_errors_flat)) == 0

        # Messages display for number of selected entities
        if valid and entity_count_ZOA == 1:
            ZOALuxembourg.main.qgis_interface.messageBar().clearWidgets()
            ZOALuxembourg.main.qgis_interface.messageBar().pushSuccess(QCoreApplication.translate('DataChecker','Success'),
                                                                       QCoreApplication.translate('DataChecker','No errors found on entities that intersect {} selected entity in ZOA MODIFICATION layer').format(entity_count_ZOA))
        elif valid and entity_count_ZOA == 0 :
            ZOALuxembourg.main.qgis_interface.messageBar().clearWidgets()
            ZOALuxembourg.main.qgis_interface.messageBar().pushSuccess(QCoreApplication.translate('DataChecker_no','Success'),
                                                                       QCoreApplication.translate('DataChecker_no','No errors found'))
        elif valid and entity_count_ZOA > 1 :
            ZOALuxembourg.main.qgis_interface.messageBar().clearWidgets()
            ZOALuxembourg.main.qgis_interface.messageBar().pushSuccess(QCoreApplication.translate('DataChecker_many','Success'),
                                                                       QCoreApplication.translate('DataChecker_many','No errors found on entities that intersect {} selected entities in ZOA MODIFICATION layer').format(entity_count_ZOA))

        else:
            self.dlg = ErrorSummaryDialog(layer_structure_errors, data_errors)
            self.dlg.show()

        return valid

    # Datatype mapping allowed while checking. For a given XSD type, several QGIS type may be allowed or compatible
    XSD_QGIS_ALLOWED_DATATYPE_MAP = [(DataType.STRING, 'string'),
                                     (DataType.STRING, 'integer'),
                                     (DataType.STRING, 'double'),
                                     (DataType.INTEGER, 'integer'),
                                     (DataType.DOUBLE, 'double'),
                                     (DataType.DOUBLE, 'integer'),
                                     (DataType.DATE, 'date')]

    def checkLayerStructure(self, layer, xsd_type):
        '''
        Checks a layer structure against the XSD type
        Missing field, data type mismatch

        :param layer: The vector layer to check
        :type layer: QgsVectorLayer

        :param type: XSD schema type
        :type type: ZOAType

        :returns: A list of warning and fatal error
        :rtype: Tuple : warning, fatal. Layer (QgsVectorLayer), field (ZOAField), message (str, QString)
        '''

        native_fields = ZOALuxembourg.main.current_project.getNativeFields(xsd_type)
        warn_errors = list()
        fatal_errors = list()

        # Check geometry type
        if xsd_type.geometry_type is not None and XSD_QGIS_GEOMETRYTYPE_MAP[xsd_type.geometry_type] != layer.wkbType():
            fatal_errors.append((layer, None, QCoreApplication.translate('DataChecker', 'Geometry type mismatch, expected : {}').format(xsd_type.geometry_type)))

        # Check field structure
        for field in xsd_type.fields:
            # Check field missing
            if self._getNativeField(native_fields, field.name) == None:
                if field.nullable:
                    warn_errors.append((layer, field, QCoreApplication.translate('DataChecker', 'Nullable field is missing')))
                else:
                    warn_errors.append((layer, field, QCoreApplication.translate('DataChecker', 'Non nullable field is missing')))

                continue

            # Check field datatype
            layer_field_name, layer_field_type = self._getNativeField(native_fields, field.name)
            found = False
            for xsd_type, qgis_type in self.XSD_QGIS_ALLOWED_DATATYPE_MAP:
                if layer_field_type.lower() == qgis_type.lower() and field.type.lower() == xsd_type.lower():
                    found = True
                    break

            if not found:
                fatal_errors.append((layer, field, QCoreApplication.translate('DataChecker', 'Field datatype mismatch, expected : {}').format(field.type)))

        return warn_errors, fatal_errors

    def _getNativeField(self, fields, name):
        '''
        Get a native field  from name
        '''
        for field in fields:
            if field[0] == name:
                return field

        return None

    def checkLayerData(self, selection_ZOA, layer, xsd_type):
        '''
        Checks the data of a layer against the XSD type

        :param selection_ZOA: Selected features from the ZOA Modification layer
        :type selection_ZOA: QgsFeatureList

        :param layer: The vector layer to check
        :type layer: QgsVectorLayer

        :param type: XSD schema type
        :type type: ZOAType

        :returns: A list of data error
        :rtype: Tuples : Layer (QgsVectorLayer), list of tuple Feature (QgsFeature), field (ZOAField), message (str, QString)
        '''

        errors = list()
        areas = []

        # Check if a selection exists in 'ZOA MODIFICATION'
        if len(selection_ZOA) > 0 :

            # Selection by intersection with 'ZOA MODIFICATION' layer
            for ZOA_feature in selection_ZOA:
                cands = layer.getFeatures()
                for layer_features in cands:
                    if ZOA_feature.geometry().intersects(layer_features.geometry()):
                        areas.append(layer_features.id())

            if layer.wkbType() == QgsWkbTypes.NoGeometry:
                layer.selectAll()
            else:
                layer.select(areas)
            selection_entities_from_ZOA = layer.selectedFeatures()

            for feature in selection_entities_from_ZOA:
                errors += self.checkFeatureData(feature, xsd_type)

        else:

            for feature in layer.dataProvider().getFeatures():
                errors += self.checkFeatureData(feature, xsd_type)

        return layer, errors

    def checkFeatureData(self, feature, xsd_type):
        '''
        Checks the data of a feature against the XSD type

        :param feature: The feature to check
        :type feature: QgsFeature

        :param type: XSD schema type
        :type type: ZOAType

        :returns: A list of  error
        :rtype: List of tuples : Feature (QgsFeature), field (ZOAField), message (str, QString)
        '''

        errors = list()

        # Check geometry
        if xsd_type.geometry_type is not None:
            errors += self.checkFeatureGeometry(feature)

        for field in feature.fields():
            xsd_field = xsd_type.getField(field.name())

            # Check if field exists in XSD
            if xsd_field is None:
                continue

            errors += self.checkFeatureFieldData(feature, xsd_field)

        return errors

    def checkFeatureFieldData(self, feature, xsd_field):
        '''
        Checks the data of a feature against the XSD type

        :param feature: The feature to check
        :type feature: QgsFeature

        :param xsd_field: XSD type field
        :type xsd_field: ZOAField

        :returns: A list of  error
        :rtype: List of tuples : Feature (QgsFeature), field (ZOAField), message (str, QString)
        '''

        errors = list()

        field_value = feature.attribute(xsd_field.name)

        # Check null value
        if field_value is None or field_value == NULL:
            if not xsd_field.nullable:
                errors.append((feature, xsd_field, QCoreApplication.translate('DataChecker', 'Null value in non nullable field')))

            return errors

        # Check numeric values
        if xsd_field.type in [DataType.INTEGER,DataType.DOUBLE]:
            numeric_value = float(field_value)

            # Check min value
            if xsd_field.minvalue is not None:
                min_value = float(xsd_field.minvalue)
                if numeric_value < min_value:
                    errors.append((feature, xsd_field, QCoreApplication.translate('DataChecker', 'Value ({}) less than minimum value ({})').format(numeric_value, min_value)))

            # Check max value
            if xsd_field.maxvalue is not None:
                max_value = float(xsd_field.maxvalue)
                if numeric_value > max_value:
                    errors.append((feature, xsd_field, QCoreApplication.translate('DataChecker', 'Value ({}) greater than maximum value ({})').format(numeric_value, max_value)))

        # Check string values
        if xsd_field.type == DataType.STRING:
            text_value = str(field_value)

            # Check value length
            if xsd_field.length is not None:
                text_length = len(text_value)
                max_length = int(xsd_field.length)
                if text_length > max_length:
                    errors.append((feature, xsd_field, QCoreApplication.translate('DataChecker', 'Text length ({}) greater than field length ({})').format(text_length, max_length)))

            # Check enumeration
            if xsd_field.listofvalues is not None:
                if text_value not in xsd_field.listofvalues:
                    errors.append((feature, xsd_field, QCoreApplication.translate('DataChecker', 'Text ({}) not in field list of values').format(text_value)))
            
            # Check file exists
            if xsd_field.name == "NOM_FICHIER":
                if os.path.exists(text_value) == False:
                    errors.append((feature, xsd_field, QCoreApplication.translate('DataChecker', 'File ({}) does not exist').format(text_value)))

        return errors

    def checkFeatureGeometry(self, feature):
        '''
        Checks the geometry of a feature

        :param feature: The feature to check
        :type feature: QgsFeature

        :returns: A list of  error
        :rtype: List of tuples : Feature (QgsFeature), field (ZOAField), message (str, QString)
        '''

        errors = list()

        if feature.geometry() is None or feature.geometry().isEmpty():
            errors.append((feature, None, QCoreApplication.translate('DataChecker', 'Geometry is empty')))
        else:
            errors2 = feature.geometry().validateGeometry()

            for error in errors2:
                errors.append((feature, None, error.what()))

        return errors