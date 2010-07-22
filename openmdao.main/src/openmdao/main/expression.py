"""
A public variable that references another member of the OpenMDAO model
hierarchy.
"""

#public symbols
__all__ = ['Expression', 'ExpressionList']


# pylint: disable-msg=E0611,F0401
from enthought.traits.api import BaseStr, List, TraitError
from enthought.traits.trait_handlers import NoDefaultSpecified

from openmdao.main.expreval import ExprEvaluator

class DumbDefault(object):
    """Dummy object for default, when none is given."""
    def get_referenced_varpaths(self):
        return set()

    def get_referenced_compnames(self):
        return set()
    
    def refs_valid(self):
        return True
    
    def evaluate(self):
        raise TraitError('Expression: string reference is undefined')
        
    def set(self, val):
        raise TraitError('Expression: string reference is undefined')
            
class Expression(BaseStr):
    """A trait that references, via a pathname, another trait in the
    framework. If it has iotype of 'out', then the string may only be the
    pathname of a single variable (with optional array indexing), but if
    iotype is 'in', it may be any valid expression and may reference any
    number of other variables.
    """
    
    def __init__(self, default_value=NoDefaultSpecified, iotype=None,
                 desc=None, **metadata):
        
        if default_value is NoDefaultSpecified:
            default_value = DumbDefault()
        else:
            defval = default_value
            default_value = ExprEvaluator(default_value) # try block around this seems to do nothing ???
            
        # Put iotype in the metadata dictionary
        if iotype is not None:
            metadata['iotype'] = iotype
            
        # Put units in the metadata dictionary
        if desc is not None:
            metadata['desc'] = desc
    
        super(Expression, self).__init__(default_value, **metadata)

    def validate(self, obj, name, value):
        """ Validates that a specified value is valid for this trait.
        
        Note: The 'fast validator' version performs this check in C.
        """
        # normal string validation
        s = super(Expression, self).validate(obj, name, value)
        
        try:
            if self.iotype == 'out':
                s = ExprEvaluator(s, obj, single_name=True)
            else:
                s = ExprEvaluator(s, obj)
            s._parse()
        except Exception:
            raise TraitError("invalid %sput ref variable value '%s'" % \
                             (self.iotype, str(value)))
        
        obj.config_changed()

        return s
    
    
class ExpressionList(List):
    """A List of Expression traits."""
    
    def __init__(self, **metadata):
        self.iotype = metadata.get('iotype', 'in')
        super(ExpressionList, self).__init__(trait=Expression(
                            iotype=self.iotype), **metadata)
    
