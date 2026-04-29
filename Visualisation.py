#!/usr/bin/env python
import subprocess

from optparse import OptionParser
import os,sys
cur = os.path.dirname( os.path.realpath( __file__ ) )

#sys.path.append(cur+'/UtilityLib')
import UtilityLib.moduleStartUp as mStartUp



def main():    
    print("")
    print('=====================================')
    print('#    STARFiSh_v0.4 Visualisation    #')
    print('=====================================')
    print("")
    
    optionsDict = mStartUp.parseOptions(['f','n','v'], visualisationOnly = True)
    
    networkName    = optionsDict['networkName']
    dataNumber     = optionsDict['dataNumber']
    vizOutput      = optionsDict['vizOutput']
    if vizOutput == 'non':
        vizOutput = "2D+3D"
        

    string1 = ' '.join([sys.executable, cur+'/VisualisationLib/class2dVisualisation.py', '-f', networkName, '-n',dataNumber, '-c']) 
    string2 = ' '.join([sys.executable, '-m', 'VisualisationLib.class3dVisualisation', '-f', networkName, '-n',dataNumber, '-c True']) 

    skip_3d = os.environ.get('STARFISH_SKIP_3D', '').lower() in ('1', 'true', 'yes', 'on')
    if skip_3d:
        print("INFO: STARFISH_SKIP_3D enabled; 3D visualisation will be skipped.")
    else:
        try:
            import platform
            arch = platform.machine().lower()
            plat = sys.platform.lower()
            if plat.startswith('darwin') and arch in ('arm64', 'aarch64'):
                print("WARNING: macOS Apple Silicon detected. 3D visualisation uses legacy OpenGL and may fail on arm64.")
                print("  If you see runtime OpenGL/pyglet errors, options:")
                print("   - Disable 3D: export STARFISH_SKIP_3D=1")
                print("   - Install arm64 Miniforge/Miniconda, then run macdeps.sh to install dependencies (freeglut, pyglet==1.5.27, PyOpenGL)")
                print("   - Install Homebrew and run: brew install freeglut pkg-config graphviz")
            elif plat.startswith('darwin'):
                print("NOTE: macOS detected. 3D visualisation may require system libraries (freeglut) and pyglet 1.5.x.")
                print("  If you encounter errors, set STARFISH_SKIP_3D=1 to disable 3D or follow the instructions in macdeps.sh.")
            elif plat.startswith('linux'):
                print("NOTE: Linux detected. Ensure system OpenGL/freeglut and python packages (pyglet==1.5.27, PyOpenGL) are installed.")
            else:
                print("NOTE: 3D visualisation depends on native OpenGL libraries and may not be available on this platform.")
        except Exception:
            print("NOTE: Unable to determine platform; 3D visualisation may require native OpenGL/support libs.")
    
    if vizOutput == "2D":
        
        viz2d = subprocess.Popen(string1, shell = True )
            
    if vizOutput == "3D":
        if not skip_3d:
            viz3d = subprocess.Popen(string2, shell = True )
        
    if vizOutput == "2D+3D":
        
        viz2d = subprocess.Popen(string1, shell = True )
        viz3d = None
        if not skip_3d:
            viz3d = subprocess.Popen(string2, shell = True )
        
        while True:
            
            if viz2d.poll() != None:
                if viz3d is not None:
                    viz3d.terminate()
                exit()
                
            if viz3d is not None and viz3d.poll() != None:
                viz2d.terminate()
                exit()
                
if __name__ == '__main__':
    main()
