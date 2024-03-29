'''
Created on 01 mai 2021

@author: CNRA, arxit
'''
from __future__ import absolute_import

from builtins import range
import os
import os.path
from collections import OrderedDict
#from pyspatialite import dbapi2 as db
import sqlite3
from qgis import utils

from qgis.core import *
from qgis.PyQt.QtCore import QFileInfo, QVariant, QObject, pyqtSignal, QSettings
from qgis.PyQt.QtWidgets import QMessageBox

from . import main
from ZOALuxembourg.schema import *
from ZOALuxembourg.widgets.stylize.stylize import *
from ZOALuxembourg.widgets.topology.topology import *
import io

FILENAME = 'zoa-project.qgs'
DATABASE = 'zoa-database.sqlite'
PK = 'OGC_FID'
IMPORT_ID = 'ImportId'

class Project(QObject):
    '''
    A class which represent a ZOA project
    '''

    ready = pyqtSignal()

    def __init__(self):
        '''
        Constructor
        '''
        super(Project, self).__init__()
        self.creation_mode = False

    def open(self):
        '''
        Called when a QGIS project is opened
        '''

        # Signal QgsInterface.projectRead seems to be emited twice
        if QgsProject is None:
            return

        # QGIS emits projectRead when creating a new project
        if self.creation_mode:
            return

        # Setting
        filename = QgsProject.instance().fileName()
        self.folder = os.path.normpath(os.path.dirname(filename))
        self.filename = os.path.normpath(filename)
        self.database = os.path.join(self.folder, DATABASE)

        # If not ZOA project return
        if not self.isZOAProject():
            self.ready.emit()
            return

        # Update database
        self._updateDatabase()

        # Update map layers
        self._updateMapLayers()

        # Topological settings
        self._setupTopologicalSettings()

        # Activate the auto Show feature form on feature creation
        self._activateAutoShowForm()

        QgsProject.instance().write()

        self.ready.emit()

    def create(self, folder, name):
        '''
        Creates a new projects, and loads it in the interface

        :param folder: Folder path which will contain the new project folder
        :type folder: str, QString

        :param name: Project name, will be the project folder name
        :type name: str, QString
        '''

        self.creation_mode = True

        # Create project path
        self.folder = os.path.normpath(os.path.join(folder, name))

        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

        # Create project filename
        self.filename = os.path.join(self.folder, FILENAME)
        main.qgis_interface.newProject(True)
        #main.qgis_interface.mapCanvas().setDestinationCrs(QgsCoordinateReferenceSystem(2169, QgsCoordinateReferenceSystem.EpsgCrsId)) # SRS 2169
        main.qgis_interface.mapCanvas().setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:2169")) # EPSG 2169
        QgsProject.instance().setFileName(self.filename) # Project filename

        # Flag ZOA project
        QgsProject.instance().writeEntry('ZOA', '/ProjetZOA', True)

        QgsProject.instance().write()

        # Database
        self.database = os.path.join(self.folder, DATABASE)
        self._updateDatabase()

        # Update map layers
        self._updateMapLayers()

        QgsProject.instance().write()

        # Topological settings
        self._setupTopologicalSettings()

        # Activate the auto Show feature form on feature creation
        self._activateAutoShowForm()

        self.creation_mode = False

        # Save project and add to recent projects
        main.qgis_interface.actionSaveProject().trigger()

        # Notify project is ready
        self.ready.emit()

    def isZOAProject(self):
        '''
        Indicates whether this is a ZOA project
        '''

        result, dummy = QgsProject.instance().readBoolEntry('ZOA', '/ProjetZOA', False)

        return result

    def getLayer(self, type):
        '''
        Get the map layer corresponding to the type

        :param type: XSD schema type
        :type type: ZOAType
        '''

        # Map layers in the TOC
        maplayers = QgsProject.instance().mapLayers()

        # Iterates through XSD types
        uri = self.getTypeUri(type)

        # Check whether a layer with type data source exists in the map
        for k, v in list(maplayers.items()):
            if self.compareURIs(v.source(), uri):
                return v

        return None

    def isZOALayer(self, layer):
        '''
        Checks if a layer is a ZOA layer

        :param layer: Layer to check
        :type layer: QgsVectorLayer
        '''

        for type in main.xsd_schema.types:
            uri = self.getTypeUri(type)
            if self.compareURIs(layer.source(), uri):
                return True

        return False

    def getLayerTableName(self, layer):
        '''
        Returns the table name of the layer, only if it is a ZOA layer

        :param layer: Layer to check
        :type layer: QgsVectorLayer
        '''

        if layer is None:
            return None

        if not self.isZOALayer(layer):
            return None

        return self.getUriInfos(layer.source())[1]

    def getImportLogLayer(self):
        logimport_table = ZOAType()
        logimport_table.name = 'ImportLog'

        uri = self.getTypeUri(logimport_table)
        layer = QgsVectorLayer(uri, logimport_table.friendlyName(), 'spatialite')

        if not layer.isValid():
            return None

        return layer

    def getModificationZOALayer(self):
        return self.getLayer(main.xsd_schema.getTypeFromTableName('ZOA_TA.ZOA_MODIFICATION'))

    def getNativeFields(self, type):
        '''
        Gets the native fields with type from database

        :param type: XSD schema type
        :type type: ZOAType
        '''

        conn = self._getDbConnection()

        cursor = conn.cursor()
        rs = cursor.execute("PRAGMA table_info('{}')".format(type.name))

        for i in range(len(rs.description)):
            if rs.description[i][0] == 'name':
                name_index = i
            if rs.description[i][0] == 'type':
                type_index = i

        fields = []

        for row in rs:
            fields.append((row[name_index], row[type_index]))

        cursor.close()
        del cursor

        conn.close()
        del conn

        return fields

    def _setupTopologicalSettings(self):
        # Topological editing
        QgsProject.instance().setTopologicalEditing(True)

        # Update snapping settings
        QgsProject.instance().writeEntry('Digitizing', '/SnappingMode', 'current_layer')
        QgsProject.instance().writeEntry('Digitizing', '/DefaultSnapType', 'to vertex and segment')
        QgsProject.instance().writeEntry('Digitizing', '/DefaultSnapTolerance', 10.0)
        QgsProject.instance().writeEntry('Digitizing', '/DefaultSnapToleranceUnit', QgsTolerance.Pixels)

        QgsProject.instance().snappingConfigChanged.emit(QgsSnappingConfig(QgsProject.instance()))

    def _activateAutoShowForm(self):
        settings = QSettings()
        settings.setValue("/Map/identifyAutoFeatureForm", True)

    def _updateDatabase(self):
        '''
        Updates the project database
        '''

        xsd_schema = main.xsd_schema
        createdb = not os.path.isfile(self.database)

        conn = self._getDbConnection()

        # Create database if not exist
        if createdb:
            cursor = conn.cursor()
            cursor.execute("SELECT InitSpatialMetadata(1)")
            del cursor

        # Check and update tables
        for type in xsd_schema.types:
            uri = self.getTypeUri(type)
            layer = QgsVectorLayer(uri, type.friendlyName(), 'spatialite')

            # Create layer if not valid
            if not layer.isValid():
                self._createTable(conn, type)
                layer = QgsVectorLayer(uri, type.friendlyName(), 'spatialite')

            self._updateTable(type, layer, True)

        # Check and update the import log table
        self._updateImportLogTable(conn)

        conn.close()
        del conn

    def getTypeUri(self, type):
        '''
        Gets a uri to the table according to the XSD

        :param type: XSD schema type
        :type type: ZOAType
        '''

        uri = QgsDataSourceUri()
        uri.setDatabase(self.database)
        geom_column = 'GEOMETRY' if type is not None and type.geometry_type is not None else ''
        uri.setDataSource('', type.name, geom_column, '', PK)

        return uri.uri()

    def _createTable(self, conn, type):
        '''
        Creates a new table in the spatialite database according to the XSD

        :param conn: The database connection
        :type conn: Connection

        :param type: XSD schema type
        :type type: ZOAType
        '''

        # Create table
        query = "CREATE TABLE '%s' (%s integer primary key autoincrement,"%(type.name, PK)

        # Geometry column
        if type.geometry_type is not None:
            query += "'GEOMETRY' %s,"%type.geometry_type

        query = query[:-1]+")"
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        cursor.close()
        del cursor

        # Register geometry column
        if type.geometry_type is not None:
            query = "SELECT RecoverGeometryColumn('%s','GEOMETRY',2169,'%s',2)"%(type.name, type.geometry_type)
            cursor = conn.cursor()
            cursor.execute(query)
            rep = cursor.fetchall()

            if rep[0][0] == 0:
                conn.rollback()
            else:
                conn.commit()

            cursor.close()
            del cursor

    def _updateImportLogTable(self, conn):
        '''
        Update the import table

        :param conn: The database connection
        :type conn: Connection
        '''

        # Log import table
        logimport_table = ZOAType()
        logimport_table.name = 'ImportLog'

        # Import ID field
        field = ZOAField()
        field.name = IMPORT_ID
        field.type = DataType.STRING
        field.nullable = False
        logimport_table.fields.append(field)

        # Date field
        field = ZOAField()
        field.name = 'Date'
        field.type = DataType.STRING
        field.nullable = False
        logimport_table.fields.append(field)

        # Type field
        field = ZOAField()
        field.name = 'Filename'
        field.type = DataType.STRING
        field.nullable = False
        logimport_table.fields.append(field)

        # Layers field
        field = ZOAField()
        field.name = 'Layers'
        field.type = DataType.STRING
        field.nullable = True
        logimport_table.fields.append(field)

        uri = self.getTypeUri(logimport_table)
        layer = QgsVectorLayer(uri, logimport_table.friendlyName(), 'spatialite')

        # Create table if not valid
        if not layer.isValid():
            self._createTable(conn, logimport_table)
            layer = QgsVectorLayer(uri, logimport_table.friendlyName(), 'spatialite')

        # Update fields
        self._updateTable(logimport_table, layer)

    def _updateTable(self, type, layer, add_importid=False):
        '''
        Updates the layer's table according to the XSD

        :param type: XSD schema type
        :type type: ZOAType

        :param layer: the QGIS vector layer object
        :type layer: QgsVectorLayer
        '''

        for field in type.fields:
            if layer.fields().indexFromName(field.name) < 0:
                layer.dataProvider().addAttributes([self._getField(field)])

        # Add import id field
        if add_importid:
            field = ZOAField()
            field.name = IMPORT_ID
            field.type = DataType.STRING
            field.nullable = True
            if layer.fields().indexFromName(field.name) < 0:
                layer.dataProvider().addAttributes([self._getField(field)])

        layer.updateFields()

    # Mapping between XSD datatype and QGIS datatype
    datatypeMap = XSD_QGIS_DATATYPE_MAP

    def _getField(self, zoafield):
        '''
        Creates a QGIS Field according to the XSD

        :param zoafield: XSD schema field
        :type zoafield: ZOAField

        :returns: The corresponding QGIS Field
        :rtype: QgsField
        '''

        return QgsField(zoafield.name,
                        self.datatypeMap[zoafield.type],
                        zoafield.type,
                        int(zoafield.length) if zoafield.length is not None else 0)

    def _updateMapLayers(self):
        '''
        Update layers attributes editors and add missing layers to the TOC
        '''

        # Get rules config
        config_path = os.path.join(ZOALuxembourg.main.plugin_dir,
                                   'assets',
                                   'LayerTree.json')

        f = io.open(config_path, mode='r', encoding="utf-8")
        config_file = f.read()
        config = json.loads(config_file)
        f.close()

        main.qgis_interface.messageBar().clearWidgets()

        # Process root node tree
        self._updateLayerTreeNode(config, config)

        # Add WMS basemap layer
        self._addOrthoBasemap()

        # Add topology rules
        TopologyChecker(None).updateProjectRules()

    def _updateLayerTreeNode(self, node, parentnode):
        '''
        Update a layer tree node, a lyer group

        :param node: The current node to update
        :type node: dict

        :param node: The parent node to update
        :type node: dict
        '''

        parent = QgsProject.instance().layerTreeRoot()

        if parentnode['Name'] != 'Root':
            parent = parent.findGroup(parentnode['Name'])

        treenode = parent.findGroup(node['Name']) if node['Name'] != 'Root' else QgsProject.instance().layerTreeRoot()

        if treenode is None:
            treenode = parent.addGroup(node['Name'])

        stylize = StylizeProject()

        for child in node['Nodes']:
            if child['IsGroup']:
                self._updateLayerTreeNode(child, node)
            else:
                xsd_type = main.xsd_schema.getTypeFromTableName(child['TableName'])

                # Type not found in XSD
                if xsd_type is None:
                    main.qgis_interface.messageBar().pushSuccess(QCoreApplication.translate('Project', 'Error'),
                                                                 QCoreApplication.translate('Project', ' Type not found in XSD : {}').format(child['TableName']))
                    continue

                layer = self.getLayer(xsd_type)

                # Layer is in the TOC
                if layer is None:
                    uri = self.getTypeUri(xsd_type)
                    layer = QgsVectorLayer(uri, child['Name'], 'spatialite')
                    QgsProject.instance().addMapLayer(layer, False)
                    treenode.addLayer(layer)

                # Updates layers style
                stylize.stylizeLayer(layer, xsd_type)

                # Update attributes editors
                self._updateLayerEditors(layer, xsd_type)

                # Activate the auto Show feature form on feature creation
                #TODO QGIS 2 TO 3
                #layer.setFeatureFormSuppress(QgsVectorLayer.SuppressOff)

    def _addOrthoBasemap(self):
        ortho_url = 'url=http://wmts1.geoportail.lu/opendata/service&SLegend=0&crs=EPSG:2169&dpiMode=7&featureCount=10&format=image/jpeg&layers=ortho_latest&styles='
        ortho_found = False
        for k, v in list(QgsProject.instance().mapLayers().items()):
            if v.source() == ortho_url:
                ortho_found = True
                break

        if not ortho_found:
            ortho_layer = QgsRasterLayer(ortho_url, 'Orthophoto Luxembourg', 'wms')
            QgsProject.instance().addMapLayer(ortho_layer, False)
            QgsProject.instance().layerTreeRoot().addLayer(ortho_layer)
            main.qgis_interface.mapCanvas().setExtent(ortho_layer.extent())

    def getUriInfos(self, uri):
        '''
        Gets the database and table name from uri

        :param uri: URI
        :type uri: QString

        :returns: Database and table name
        :rtype: tuple(QString, QString)
        '''

        db = ''
        table = ''
        split = uri.split(' ')
        for kv in split:
            if kv.startswith('dbname'):
                db = os.path.normpath(kv[8:-1])
            if kv.startswith('table'):
                table = kv[7:-1]

        return db, table

    def compareURIs(self, uri1, uri2):
        '''
        Compares 2 URIs

        :param uri1: URI 1
        :type uri1: QString

        :param uri2: URI 2
        :type uri2: QString

        :returns: True is the URIs point to the same table
        :rtype: Boolean
        '''

        # URI 1
        info1 = self.getUriInfos(uri1)

        # URI 2
        info2 = self.getUriInfos(uri2)

        return info1 == info2

    def _updateLayerEditors(self, layer, type):
        '''
        Update the layers attributes editors

        :param layer: The layer to update
        :type layer: QgsVectorLayer

        :param type: XSD schema type
        :type type: ZOAType
        '''
        # Hide fields
        hidden = [PK, IMPORT_ID]
        for field in layer.fields():
            if field.name() == IMPORT_ID:
                #layer.setEditorWidgetV2(layer.fields().indexFromName(field.name()), 'TextEdit')
                layer.setEditorWidgetSetup(layer.fields().indexFromName(field.name()), QgsEditorWidgetSetup("TextEdit", {}))

        ''' Bug http://hub.qgis.org/issues/14235 '''
        for field in layer.fields():
            if field.name() in hidden:
                #layer.setEditorWidgetV2(layer.fields().indexFromName(field.name()), 'Hidden')
                layer.setEditorWidgetSetup(layer.fields().indexFromName(field.name()), QgsEditorWidgetSetup("Hidden", {}))

        # Editors
        for field in type.fields:
            self._setupFieldEditor(field, layer)

    fileFields = ['NOM_FICHIER', 'NOM_EC', 'NOM_GR']

    def _setupFieldEditor(self, field, layer):
        '''
        Update the field editor

        :param zoafield: XSD schema field
        :type zoafield: ZOAField

        :param layer: The layer to update
        :type layer: QgsVectorLayer
        '''

        fieldIndex = layer.fields().indexFromName(field.name)

        if fieldIndex == -1:
            return

        config = dict()

        # String
        if field.type == DataType.STRING:
            # Simple text
            editor = 'TextEdit'

            # File
            for fileField in self.fileFields:
                if field.name.startswith(fileField):
                    editor = 'ExternalResource'
                    config = {
                        'RelativeStorage': 0
                    }

                    #editor = 'SimpleFilename'
                    
            # Enumeration
            if field.listofvalues is not None:
                editor = 'ValueMap'

                # Invert key, value of currentConfig
                #currentConfig = layer.editorWidgetV2Config(fieldIndex) if layer.editorWidgetV2(fieldIndex) == 'ValueMap' else OrderedDict()
                currentConfig = layer.editorWidgetSetup(fieldIndex).config() if layer.editorWidgetSetup(fieldIndex).type() == 'ValueMap' else OrderedDict()
                if "map" in currentConfig:
                    currentConfig["map"] = OrderedDict((v, k) for k, v in currentConfig["map"].items())

                    # Keep current values and add new ones
                    for element in field.listofvalues:
                        if element in currentConfig["map"]:
                            config[currentConfig["map"][element]] = element # Config is in the form, description, value
                        else:
                            config[element] = element
                else:
                    # Add new values
                    for element in field.listofvalues:
                        config[element] = element

        # Integer
        elif field.type == DataType.INTEGER:
            editor = 'Range'
            config = {
                'AllowNull': True,
                'Max': 100,
                'Min': 0,
                'Step': 1,
                'Style': 'SpinBox'
            }
            
            #editor = 'PreciseRange'
            #config['Min'] = int(field.minvalue) if field.minvalue is not None else -sys.maxsize-1
            #config['Max'] = int(field.maxvalue) if field.maxvalue is not None else sys.maxsize
            #config['Step'] = 1
            #config['AllowNull'] = field.nullable

        # Double
        elif field.type == DataType.DOUBLE:
            editor = 'Range'
            config = {
                'AllowNull': True,
                'Max': 100.00,
                'Min': 0,
                'Precision': 3,
                'Step': 0.1,
                'Style': 'SpinBox'
            }
            
            #editor = 'PreciseRange'
            #config['Min'] = float(field.minvalue) if field.minvalue is not None else -sys.maxsize-1
            #config['Max'] = float(field.maxvalue) if field.maxvalue is not None else sys.maxsize
            #mindecimal = len(field.minvalue.split('.')[1]) if field.minvalue is not None and len(field.minvalue.split('.')) == 2 else 0
            #maxdecimal = len(field.maxvalue.split('.')[1]) if field.maxvalue is not None and len(field.maxvalue.split('.')) == 2 else 0
            #config['Step'] = 1.0/pow(10, max(mindecimal, maxdecimal))
            #config['AllowNull'] = field.nullable

        # Date
        elif field.type == DataType.DATE:
            editor = 'DateTime'
            config['field_format'] = 'yyyy-MM-dd'
            config['display_format'] = 'yyyy-MM-dd'
            config['calendar_popup'] = True
            config['allow_null'] = field.nullable

        # Other
        else:
            raise NotImplementedError('Unknown datatype')

        #layer.setEditorWidgetV2(fieldIndex, "ValueMap")
        #layer.setEditorWidgetV2Config(fieldIndex, config)

        #editor_widget_setup = QgsEditorWidgetSetup(editor, {
        #    'map':config
        #})

        if editor in ('TextEdit', 'Range', 'ExternalResource'):
            editor_widget_setup = QgsEditorWidgetSetup(editor, config)
        elif editor in ('ValueMap', 'DateTime'):
            editor_widget_setup = QgsEditorWidgetSetup(editor, {
                'map':config
            })

        layer.setEditorWidgetSetup(fieldIndex, editor_widget_setup)

    def _getDbConnection(self):
        '''
        Gets the database connection
        '''

        if os.name == "nt":
            conn = utils.spatialite_connect(self.database)
        else:
            conn = sqlite3.connect(self.database)
            conn.enable_load_extension(True)
            conn.load_extension('/Library/Frameworks/SQLite3.framework/Versions/E/Modules/mod_spatialite.dylib')

        return conn
