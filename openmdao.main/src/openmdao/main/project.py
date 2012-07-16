"""
Routines for handling 'Projects' in Python.
"""

import os
import sys
import inspect
import tarfile
import cPickle as pickle

from pkg_resources import get_distribution, DistributionNotFound

from openmdao.main.api import Container
from openmdao.main.assembly import Assembly, set_as_top
from openmdao.main.component import SimulationRoot
from openmdao.util.fileutil import get_module_path, expand_path
from openmdao.util.log import logger

from openmdao.main.mp_support import is_instance

# extension for project files
PROJ_FILE_EXT = '.proj'


def _parse_archive_name(pathname):
    """Return the name of the project given the pathname of a project
    archive file.
    """
    if '.' in pathname:
        return '.'.join(os.path.basename(pathname).split('.')[:-1])
    else:
        return os.path.basename(pathname)


def project_from_archive(archive_name, proj_name=None, dest_dir=None):
    """Expand the given project archive file in the specified destination
    directory and return a Project object that points to the newly
    expanded project.
    
    archive_name: str
        Path to the project archive to be expanded.
        
    proj_name: str (optional)
        Name of the new project. Defaults to the name of the project contained
        in the name of the archive.
        
    dest_dir: str (optional)
        Directory where the project directory for the expanded archive will
        reside. Defaults to the directory where the archive is located.
    """
    archive_name = expand_path(archive_name)

    if dest_dir is None:
        dest_dir = os.path.dirname(archive_name)
    else:
        dest_dir = expand_path(dest_dir)
        
    if proj_name is None:
        proj_name = _parse_archive_name(archive_name)

    projpath = os.path.join(dest_dir, proj_name)
    
    if os.path.exists(projpath):
        raise RuntimeError("Directory '%s' already exists" % projpath)

    os.mkdir(projpath)
    startdir = os.getcwd()
    if os.path.getsize(archive_name) > 0:
        try:
            f = open(archive_name, 'rb')
            tf = tarfile.open(fileobj=f,mode='r')
            tf.extractall(projpath)
        except Exception, err:
            print "Error expanding project archive:",err
        finally:
            tf.close()
    proj = Project(projpath)
    return proj

#def find_distrib_for_obj(obj):
    #"""Return the name of the distribution containing the module that
    #contains the given object, or None if it's not part of a distribution.
    #"""
    #try:
        #fname = inspect.getfile(obj)
    #except TypeError:
        #return None
    
    #modpath = get_module_path(fname)
    #parts = modpath.split('.')
    #l = len(parts)
    #for i in range(l):
        #try:
            #dist = get_distribution('.'.join(parts[:l-i]))
        #except DistributionNotFound:
            #continue
        #return dist
    #return None
    
    
#def model_to_class(model, classname, stream):
    #"""Takes a model and creates a new class inherited from the model's
    #class that is initialized with the current model's non-default
    #configuration.  The class definition is written to the given stream.
    #Note that this does not save the exact state of the model, but only
    #key inputs and attributes recommended by the model and its children.
    #"""
    #cfg = model.get_configinfo()
    #cfg.save_as_class(stream, classname)


class Project(object):
    def __init__(self, projpath):
        """Initializes a Project containing the project found in the 
        specified directory or creates a new project if one doesn't exist.
        
        projpath: str
            Path to the project's directory.
        """
        macro_exec = False
        self._recorded_cmds = []
        self.path = expand_path(projpath)
        modeldir = os.path.join(self.path, 'model')
        self.activate()
        if os.path.isdir(projpath):
            # locate file containing state, create it if it doesn't exist
            statefile = os.path.join(projpath, '_project_state')
            if os.path.exists(statefile):
                try:
                    with open(statefile, 'r') as f:
                        self.__dict__.update(pickle.load(f))
                except Exception, e:
                    print 'Unable to restore project state:',e
                    self._initialize()
                    macro_exec = True
            macro_file = os.path.join(self.path, '_project_macro')
            if os.path.isfile(macro_file):
                if macro_exec:
                    print 'Attempting to reconstruct project using macro'
                self.load_macro(macro_file, execute=macro_exec)
            else:
                self._initialize()
        else:  # new project
            os.makedirs(projpath)
            os.mkdir(modeldir)
            self._initialize()
            
        self.save()

        SimulationRoot.chroot(self.path)

    def _initialize(self):
        self.top = set_as_top(Assembly())
        
    @property
    def name(self):
        return os.path.basename(self.path)
    
    def load_macro(self, fpath, execute=True, strict=False):
        with open(fpath, 'r') as f:
            for i,line in enumerate(f):
                if execute:
                    try:
                        self.command(line)
                    except Exception as err:
                        logger.error('file %s line %d: %s' % (fpath, i, str(err)))
                        if strict:
                            raise
                else:
                    self._recorded_cmds.append(line)

    def command(self, cmd):
        err = None
        try:
            compile(cmd, '<string>', 'eval')
        except SyntaxError:
            try:
                exec(cmd) in self.__dict__
            except Exception as err:
                pass
        else:
            try:
                result = eval(cmd, self.__dict__)
            except Exception as err:
                pass
            
        if err:
            self._recorded_cmds.append('#ERR: <%s>' % cmd)
            raise err
        else:
            self._recorded_cmds.append(cmd)
            
    def activate(self):
        """Puts this project's directory on sys.path."""
        modeldir = os.path.join(self.path, 'model')
        if modeldir not in sys.path:
            sys.path = [modeldir]+sys.path
        
    def deactivate(self):
        """Removes this project's directory from sys.path."""
        modeldir = os.path.join(self.path, 'model')
        try:
            sys.path.remove(modeldir)
        except:
            pass

    def save(self):
        """ Save the state of the project to its project directory.
            Currently only Containers found in the project are saved.
        """
        fname = os.path.join(self.path, '_project_state')
        # copy all openmdao containers to a new dict for saving
        save_state = {}
        for k in self.__dict__:
            if is_instance(self.__dict__[k], Container):
                save_state[k] = self.__dict__[k]
        try:
            with open(fname, 'wb') as f:
                pickle.dump(save_state, f)
        except Exception as err:
            logger.error("Failed to pickle the project: %s" % str(err))
            
        if self._recorded_cmds:
            logger.info("Saving macro used to create project")
            with open(os.path.join(self.path, '_project_macro'), 'w') as f:
                self._write_macro_header(f)
                for cmd in self._recorded_cmds:
                    f.write(cmd)
                    f.write('\n')
        
    def _write_macro_header(self, f):
        header = [
            'from openmdao.main.factorymanager import create',
        ]
        for line in header:
            f.write(line+'\n')
        
    def export(self, projname=None, destdir='.'):
        """Creates an archive of the current project for export. 
        
        projname: str (optional)
            The name that the project in the archive will have. Defaults to
            the current project name.
        
        destdir: str (optional)
            The directory where the project archive will be placed. Defaults to
            the current directory.
        """
        
        ddir = expand_path(destdir)
        if projname is None:
            projname = self.name
        projpath = os.path.join(ddir, projname)
        
        if ddir.startswith(self.path):  # the project contains the dest directory... bad
            raise RuntimeError("Destination directory for export (%s) is within project directory (%s)" %
                               (ddir, self.path))
        
        self.save()
        startdir = os.getcwd()
        os.chdir(self.path)
        try:
            try:
                fname = os.path.join(ddir,projname+PROJ_FILE_EXT)
                f = open(fname, 'wb')
                tf = tarfile.open(fileobj=f,mode='w:gz')
                for entry in os.listdir(self.path):
                    tf.add(entry)
            except Exception, err:
                print "Error creating project archive:",err
            finally:
                tf.close()
        finally:
            os.chdir(startdir)
