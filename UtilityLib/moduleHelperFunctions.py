import os
import subprocess

try:
    import psutil
except Exception:
    psutil = None

def memoryUsagePsutil():
    '''
    evaluate the current memory usage from psutils
    
    Returns: memory currently used in MB
    '''
    if psutil is None:
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        except Exception:
            return 0.0
    process = psutil.Process(os.getpid())
    return process.memory_info()[0] / float(2 ** 20)

def getGitHash():
    '''
    This function evaluates the actual branch and leatest git commit hash
    to create an unique version reference for xml files
    
    
    Returns: git hash (str): latest git commit hash
    '''
   
    #branchName   = subprocess.check_output(["git", "describe",'--all'])
    
    try:
        gitHash = subprocess.check_output("git rev-parse HEAD", shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(e)
        gitHash = "not available"
    
    gitHash  = gitHash.split('\n')[0]
    
    # if 0 no changes otherwise uncommitted changes exist
    try:
        dirtyRepos = subprocess.check_output("git diff --quiet --exit-code", shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(e)
        dirtyRepos = True
        print("""WARNING: moduleHelperFunctions.getGitHash(): uncommited changes detected,
         git hash does not correspond to actual code version!""")
        gitHash = ' '.join([gitHash, 'uncomitted changes'])
    
    return gitHash