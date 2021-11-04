# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ZOALuxembourg
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
 This script initializes the plugin, making it known to QGIS.
"""
from __future__ import absolute_import


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load ZOALuxembourg class from file ZOALuxembourg.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .main import ZOALuxembourg
    return ZOALuxembourg(iface)
