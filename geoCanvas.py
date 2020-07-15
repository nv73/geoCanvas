from PyQt5 import QtWidgets, QtGui, QtCore
from PIL import Image, ImageQt
import gdal
import numpy as np
import osr

class geoCanvas(QtWidgets.QGraphicsView):
    
    photoClicked = QtCore.pyqtSignal(QtCore.QPoint)
    
    patchAdded = QtCore.pyqtSignal(str)

    def __init__(self):

        super(geoCanvas, self).__init__()
        
        # Initialize the scene for the graphics view
        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)

        self._QtImage = QtWidgets.QGraphicsPixmapItem()

        # QGraphicsView properties
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setMouseTracking(True)

        # some helper variables
        self._empty = True
        self._zoom = 0

        # Holder for geoImages
        self.geoImage = {}
        self.geoImage_index = 0
        
        #Holder for selected Areas
        self.patches = {}
        self.patch_index = 0

        # Coordinate values for the mouse cursor
        self.mouse_coordinates = None
        self.selected_coordinates = None

        # Graphical coordinate indicators
        self.displayed_coordinates = QtWidgets.QGraphicsTextItem()
        self.displayed_coordinates.setTransformOriginPoint(self.displayed_coordinates.boundingRect().topLeft())
        self.displayed_coordinates_font = self.displayed_coordinates.font()
        self.displayed_coordinates_font.setPointSize(20)
        self.displayed_coordinates.setFont(self.displayed_coordinates_font)
        self.displayed_coordinates_scale = 1

        # Add the initialized image and text to the graphics view
        self.scene.addItem(self._QtImage)
        self.scene.addItem(self.displayed_coordinates)

    # Taken from https://stackoverflow.com/questions/35508711/how-to-enable-pan-and-zoom-in-a-qgraphicsvie
    def setQtImage(self, pixmap=None):

        self._zoom = 0

        if pixmap and not pixmap.isNull():

            self._empty = False

            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)

            self.viewport().setCursor(QtCore.Qt.CrossCursor)

            self._QtImage.setPixmap(pixmap)

        else:

            self._empty = True

            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

            self._QtImage.setPixmap(QtGui.QPixmap())

        self.fitInView()

    def hasQtImage(self):

        return not self._empty

    # Taken from https://stackoverflow.com/questions/35508711/how-to-enable-pan-and-zoom-in-a-qgraphicsview
    def fitInView(self, scale=True):

        rect = QtCore.QRectF(self._QtImage.pixmap().rect())

        if not rect.isNull():

            self.setSceneRect(rect)

            if self.hasQtImage():
                
                unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))

                self.scale(1 / unity.width(), 1 / unity.height())

                viewrect = self.viewport().rect()

                scenerect = self.transform().mapRect(rect)

                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())

                self.scale(factor, factor)

            self._zoom = 0

    def wheelEvent(self, event):

        if not self._empty:

            if event.angleDelta().y() > 0:

                factor = 1.25

                self._zoom += 1

                self.displayed_coordinates.setScale(self.displayed_coordinates_scale)

                self.displayed_coordinates_scale = self.displayed_coordinates_scale * 0.8

            else:

                if self.displayed_coordinates_scale < 1.0:

                    self.displayed_coordinates_scale = self.displayed_coordinates_scale * 1.25

                factor = 0.8

                self._zoom -= 1

                self.displayed_coordinates.setScale(self.displayed_coordinates_scale)

            if self._zoom > 0:

                self.scale(factor, factor)

            elif self._zoom == 0:

                self.fitInView()

            else:

                self._zoom = 0

    def enterEvent(self, event):

        self.viewport().setCursor(QtCore.Qt.CrossCursor)

        super(geoCanvas, self).enterEvent(event)

    def mousePressEvent(self, event):
        
        if self._QtImage.isUnderMouse():
            
            self.photoClicked.emit(QtCore.QPoint(event.pos()))

        selected_coordinates = self.mapToScene(event.x(), event.y())

        self.selected_coordinates = (selected_coordinates.x(), selected_coordinates.y())

        self.viewport().setCursor(QtCore.Qt.CrossCursor)
        
        #Draw rectangle on a shift click input
        if QtWidgets.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
            
            rect = QtWidgets.QGraphicsRectItem(0,0, 10,10)
            
            rect.setPos(selected_coordinates.x() - 5, selected_coordinates.y() - 5)
            
            self.patches[self.patch_index] = rect
            
            self.patch_index += 1
            
            self.scene.addItem(rect)

        super(geoCanvas, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):

        super(geoCanvas, self).mouseReleaseEvent(event)

        self.viewport().setCursor(QtCore.Qt.CrossCursor)

    def mouseMoveEvent(self, event):

        mouse_coords = self.mapToScene(event.x(), event.y())

        self.mouse_coordinates = (mouse_coords.x(), mouse_coords.y())

        self.displayed_coordinates.setPlainText("X: %i, Y: %i" % (mouse_coords.x(), mouse_coords.y()))

        self.displayed_coordinates.setPos(mouse_coords.x(), mouse_coords.y())

        super(geoCanvas, self).mouseMoveEvent(event)

    def toggleDragMode(self):

        if self.dragMode() == QtWidgets.QGraphicsView.ScrollHandDrag:

            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

        elif not self.QtImage.pixmap().isNull():

            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)

    # Convert a PIL image to a QPixmap
    def imageToQPixmap(self, image):

        imgQt = QtGui.QImage(ImageQt.ImageQt(image))

        qPixMap = QtGui.QPixmap.fromImage(imgQt)

        return (qPixMap)

    # Display a 2d array within the viewport (no georeferencing)
    def displayArray(self, arr):
        
        input_array = abs(np.array(arr))
        
        try:
            
            input_array[abs(input_array) > 50000.00] = np.nan
            
        except Exception as e:
            
            pass
        
        if len(arr.shape) != 2:

            print("Input must be 2-dimensional array.")

        else:
            
            img = Image.fromarray(((input_array / np.nanmax(input_array)) * 255).astype('uint8'), mode='L')
                
            imgPixMap = self.imageToQPixmap(img)

            self.setQtImage(imgPixMap)

    # Load a geoimage in gdal format into a dictionary
    # Using the dictionary allows for multiple rasters to be loaded at once

    def importGeoImage(self, geoImagePath=None):

        if geoImagePath == None:

            geoImagePath = QtWidgets.QFileDialog.getOpenFileName(self, "Import GeoImage", "", ".tif(*.tif)")
            
            geoImagePath = str(geoImagePath)
            
            self.geoImage[geoImagePath] = geoImageReference(geoImagePath)

        else:

            self.geoImage[geoImagePath] = geoImageReference(geoImagePath)
            
    def getGeodetics(self, inputGeoImage):
        
        geoTransform = inputGeoImage.GetGeoTransform()
        projection = inputGeoImage.GetProjection()
        
        return(geoTransform, projection)
        
    def displayGeoImage(self, geoImageFilePath, band=1):
        
        geoImage = gdal.Open(geoImageFilePath)
        
        imageGeodetics = (geoImage.GetProjection(), geoImage.GetGeoTransform())
        
        bandForDisplay = geoImage.GetRasterBand(band)
        
        arrayFromGeoImageBand = bandForDisplay.ReadAsArray(0,0, geoImage.RasterXSize, geoImage.RasterYSize)

#Extracts useful information from geo imagery, stores it, and closes the geoimage file
#This is used to be able to save and access the relevant metadata, without clogging
#up memory. This allows us to load only the files we want into memory when we need them
#by using the filename
class geoImageReference(object):

    def __init__(self, geoImagePath):
        
        gImage = gdal.open(geoImagePath)
        
        prj = gImage.GetProjection()
        
        gt = gImage.GetGeoTransform()
        
        srs = osr.SpatialReference(wkt=prj)
        
        gImage = None
        
        self.filePath = geoImagePath
        
        self.projectedCoordinateSystem = srs.GetAttrValue('projcs')
        
        self.geoCoordinateSystem = srs.GetAttrValue('geogcs')
        
        self.datum = srs.GetAttrValue('datum')
        
        self.spherioid = srs.GetAttrValue('spheroid')
        
        self.projection = srs.GetAttrValue('projection')
        
        self.x = gt[0]
        
        self.y = gt[3]
        
        self.resolution = gt[1]
        
        self.spatialReferenceSystem = srs
        
        self.geoTransform = gt