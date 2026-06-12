try:
    import gtk
    import gobject
except Exception:
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('GObject', '2.0')
        from gi.repository import Gtk as gtk
        from gi.repository import GObject as gobject
        if not hasattr(gtk, 'WIN_POS_CENTER') and hasattr(gtk, 'WindowPosition'):
            gtk.WIN_POS_CENTER = gtk.WindowPosition.CENTER
        # Compatibility wrappers for GTK3 when code uses old GTK2 constructors.
        class _VBox(gtk.Box):
            def __init__(self, homogeneous=False, spacing=0):
                super().__init__(orientation=gtk.Orientation.VERTICAL, spacing=spacing)
            def pack_start(self, child, expand=True, fill=True, padding=0):
                super().pack_start(child, expand, fill, padding)
        gtk.VBox = _VBox
        class _Alignment(gtk.Alignment):
            def __init__(self, xalign=0, yalign=0, xscale=1, yscale=1):
                super().__init__()
                try:
                    self.set(xalign, yalign, xscale, yscale)
                except Exception:
                    pass
        gtk.Alignment = _Alignment
    except Exception:
        # Provide lightweight stubs so the module can be imported on systems
        # without GTK. This disables realtime visualisation but avoids
        # import-time crashes elsewhere in the program.
        class _DummyWindow:
            def __init__(self, *args, **kwargs):
                pass
            def set_size_request(self, *a, **k):
                pass
            def set_position(self, *a, **k):
                pass
            def connect(self, *a, **k):
                pass
            def add(self, *a, **k):
                pass
            def show_all(self, *a, **k):
                pass

        class _DummyGtkModule:
            Window = _DummyWindow
            WIN_POS_CENTER = 0
            VBox = object
            Alignment = object
            def main_quit(self, *a, **k):
                return None

        class _DummyGObject:
            @staticmethod
            def timeout_add(*a, **k):
                return False

        gtk = _DummyGtkModule()
        gobject = _DummyGObject()
from optparse import OptionParser
from matplotlib.figure import Figure
# Select a suitable FigureCanvas backend. Try GTK backends first, then
# fall back to the non-interactive Agg backend so the module can be
# imported on headless systems.
CANVAS_IS_GTK = True
try:
    # GTK2 agg backend (older matplotlib)
    from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
except Exception:
    try:
        # GTK3 backend
        from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
    except Exception:
        # Fallback: Agg (non-GUI)
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
        CANVAS_IS_GTK = False
import numpy as np
import os
cur = os.path.dirname( os.path.realpath( __file__ ) )



class realTimeVisualisation(gtk.Window):

    def __init__(self,networkVariables):
        '''

        '''
        super(realTimeVisualisation,self).__init__()

        self.set_size_request(640,690)
        self.set_position(gtk.WIN_POS_CENTER)
        self.connect("destroy", gtk.main_quit)

        self.fig = Figure(figsize=(5,4), dpi=100)
        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        self.canvas.set_size_request(640,690)

        vbox = gtk.VBox(False,1)
        alignIm = gtk.Alignment(0, 1 , 1, 0)
        alignIm.add(self.canvas)
        vbox.pack_start(alignIm)


        self.add(vbox)

        self.initNetworkVariables(networkVariables)
        self.createGraph()
        updateTime = 1 #len(self.quantitiesToPlot) ## if this time is to fast, it will show nothing
        gobject.timeout_add(updateTime,self.updateGraph)

        self.show_all()


    def initNetworkVariables(self,networkVariables):
        '''

        '''
        self.dt               = 0.01
        self.filename         = '../.realtime.viz'
        self.quantitiesToPlot = ['Pressure','Flow']
        self.initialValues    = [0,0,0,0,0]

        #TODO: Try Except Pass should be fixed
        try:
            self.dt               =  networkVariables['dt']
            self.filename         =  networkVariables['filename']
            self.quantitiesToPlot =  networkVariables['quantitiesToPlot']
            self.initialValues    =  networkVariables['initialValues']
        except: pass

    def updateGraph(self):
        '''

        '''

        #TODO: Try Except Pass should be fixed
        try:
            with open(''.join([cur,'/',self.filename]),'r') as dataFile:
                for dataLine in dataFile:
                    dataString = dataLine
                    break
            os.remove(''.join([cur,'/',self.filename]))
        except: pass

        dataDict = {}

        #TODO: Try Except Pass should be fixed
        try:
            dataDict = eval(dataString)
        except:
            try:
                if dataString == 'STOP':
                    return False
            except: pass
            pass


        #TODO: Try Except Pass should be fixed
        try:
            for quantity in self.quantitiesToPlot:
                newValue = dataDict[quantity]
                ## update y values
                yvals = self.lines[quantity].get_ydata()
                yvalsn = np.append(yvals,newValue)
                self.lines[quantity].set_ydata(yvalsn)
                ## update x values
                timeOld = self.lines[quantity].get_xdata()
                time = np.append(timeOld,[timeOld[-1]+self.dt])
                self.lines[quantity].set_xdata(time)
                ## adjust limits
                self.adjustAxis(self.axis[quantity],time,yvalsn)

            # update view()
            self.canvas.figure = self.fig
            self.fig.set_canvas(self.canvas)
            self.canvas.queue_resize()
        except: pass

        return True


    def adjustAxis(self,axis,xVals,yVals):
        '''

        '''
        mmF = 0.1
        #get values for y
        yMaxVals = np.max(yVals)
        yMinVals = np.min(yVals)
        yMinAx,yMaxAx = axis.get_ylim()

        #check and correct if necessary
        if yMaxVals > yMaxAx-mmF*abs(yMaxAx):
            yMaxAx = yMaxVals+mmF*abs(yMaxVals)
        if yMinVals < yMinAx+mmF*abs(yMinAx):
            yMinAx = yMinVals-mmF*abs(yMinVals)
        #apply y values

        axis.set_ylim([yMinAx,yMaxAx])
        #get values for x
        xMinVals = np.min(xVals)
        xMaxVals = np.max(xVals)
        xMinAx,xMaxAx = axis.get_xlim()
        #check and correct if necessary
        if xMaxVals > xMaxAx-mmF*abs(xMaxAx):
            xMaxAx = xMaxVals+mmF*abs(xMaxVals)
        if xMinVals < xMinAx+mmF*abs(xMinAx):
            xMinAx = xMinVals-mmF*abs(xMinVals)
        #apply y values
        axis.set_xlim([xMinAx,xMaxAx])

    def createGraph(self):
        '''

        '''
        numberOfQuantities = len(self.quantitiesToPlot)

        self.fig.subplots_adjust(hspace  = 0.4)
        self.fig.subplots_adjust(right   = 0.85)
        self.fig.subplots_adjust(top     = 0.98)
        self.fig.subplots_adjust(bottom  = 0.2)
        self.fig.subplots_adjust(hspace  = 0.5)
        self.fig.set_figwidth(8.27)
        self.fig.set_figheight((11.69/3)*numberOfQuantities)

        self.lines = {}
        self.axis = {}

        i = 0
        colors = ['b','r','m','g','k']
        for quantity in self.quantitiesToPlot:
            self.axis[quantity] = self.fig.add_subplot(numberOfQuantities,1,i+1, ylabel=quantity, xlabel='Time', ylim = [self.initialValues[i],self.initialValues[i]-0.001], xlim = [0,0.0001])
            self.lines[quantity] = self.axis[quantity].plot(0,self.initialValues[i],color=colors[i] ,linestyle = '-',label=quantity, linewidth = 1.)[0]
            i = i+1

        # update view()
        self.canvas.figure = self.fig
        self.fig.set_canvas(self.canvas)
        self.canvas.queue_resize()

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-f", "--filename", dest='filename',
                      help="set the connection-filename", metavar="FILE")
    parser.add_option("-t", "--dt", dest='dt',
                      help="set the dt of simulation", metavar="FILE")
    parser.add_option("-q", "--quantitiesToPlot", dest='quantitiesToPlot',
                      help="set the quantitiesToPlot", metavar="FILE")
    parser.add_option("-i", "--initialValues", dest='initialValues',
                      help="set the initialValues", metavar="FILE")

    (options, args) = parser.parse_args()
    networkVariables = {}

    if options.filename != None:
        networkVariables['filename'] = options.filename
    if options.dt != None:
        networkVariables['dt'] = float(options.dt)
    if options.quantitiesToPlot != None:
        networkVariables['quantitiesToPlot'] = options.quantitiesToPlot.split('-')
    if options.initialValues != None:
        networkVariables['initialValues'] = [float(i) for i in options.initialValues.split('=')]

    realTimeVisualisation(networkVariables)
    gtk.main()
