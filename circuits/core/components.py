# Package:  components
# Date:     11th April 2010
# Author:   James Mills, prologic at shortcircuit dot net dot au
from circuits.core.events import Event

"""Components

This module defines the BaseComponent and the subclass Component
"""

from types import MethodType
from collections import Callable
from inspect import getmembers, isclass

from .manager import Manager
from .utils import flatten, findroot
from .events import Registered, Unregistered
from .handlers import handler, HandlerMetaClass


def check_singleton(x, y):
    """Return True if x contains a singleton that is already a member of y"""

    singletons = filter(lambda i: getattr(i, "singleton", False), flatten(x))

    for component in singletons:
        singleton = getattr(component, "singleton", False)
        if isclass(singleton) and issubclass(singleton, Manager):
            if any([isinstance(c, singleton) for c in flatten(findroot(y))]):
                return True
        elif singleton:
            if any([type(component) in c for c in flatten(findroot(y))]):
                return True

    return False


class SingletonError(Exception):
    """Singleton Error

    Raised if a Component with the `singleton` class attribute is True.
    """

class PrepareUnregister(Event):
    """PrepareUnregister Event
    
    This event is sent when a component is about to be unregistered
    from the component tree. Unregistering a component actually
    detaches the complete subtree that the unregistered component 
    is the root of. Components that need to know if they
    are removed from the main tree (e.g. because they maintain
    relationships to other components in the tree) handle this
    event, check if the component being unregistered is one
    of their ancestors and act accordingly.
    
    :param component: the component that will be unregistered
    :type  type: :class:`~.BaseComponent`
    """
    
    complete = True
    
    def in_subtree(self, component):
        """
        Convenience method that checks if the given *component*
        is in the subtree that is about to be detached.
        """
        while True:
            if component == self.args[0]:
                return True
            if component == component.root:
                return False
            component = component.parent


class BaseComponent(Manager):
    """Base Component

    This is the base class for all components in a circuits based application.
    Components can (and should, except for root components) be registered
    with a parent component.

    BaseComponents can declare methods as event handlers using the
    handler decoration (see :func:`circuits.core.handlers.handler`). The
    handlers are invoked for matching events from the
    component's channel (specified as the component's ``channel`` attribute).

    BaseComponents inherit from :class:`circuits.core.manager.Manager`.
    This provides components with the
    :func:`circuits.core.manager.Manager.fireEvent` method that can
    be used to fire events as the result of some computation.

    Apart from the ``fireEvent()`` method, the Manager nature is important
    for root components that are started or run.
    
    :ivar channel: a component can be associated with a specific channel
        by setting this attribute. This should either be done by
        specifying a class attribute *channel* in the derived class or by
        passing a keyword parameter *channel="..."* to *__init__*. If 
        specified, the component's handlers receive events on the
        specified channel only, and events fired by the component will
        be sent on the specified channel (this behavior may be overridden,
        see :class:`~circuits.core.events.Event`, :meth:`~.fireEvent` and
        :func:`~circuits.core.handlers.handler`). By default, the channel
        attribute is set to "*", meaning that events are fired on all
        channels and received from all channels.
    """

    channel = "*"
    singleton = False

    def __new__(cls, *args, **kwargs):
        self = super(BaseComponent, cls).__new__(cls)

        handlers = dict([(k, v) for k, v in cls.__dict__.items()
                if getattr(v, "handler", False)])

        overridden = lambda x: x in handlers and handlers[x].override

        for base in cls.__bases__:
            if issubclass(cls, base):
                for k, v in list(base.__dict__.items()):
                    p1 = isinstance(v, Callable)
                    p2 = getattr(v, "handler", False)
                    p3 = overridden(k)
                    if p1 and p2 and not p3:
                        name = "%s_%s" % (base.__name__, k)
                        method = MethodType(v, self)
                        setattr(self, name, method)

        return self

    def __init__(self, *args, **kwargs):
        "initializes x; see x.__class__.__doc__ for signature"

        super(BaseComponent, self).__init__(*args, **kwargs)

        self.channel = kwargs.get("channel", self.channel) or "*"

        for k, v in getmembers(self):
            if getattr(v, "handler", False) is True:
                self.addHandler(v)
            if v is not self and isinstance(v, BaseComponent) \
                    and v not in ('parent', 'root'):
                v.register(self)

        if hasattr(self, "init") and callable(self.init):
            self.init(*args, **kwargs)

    def register(self, parent):
        if check_singleton(self, parent):
            raise SingletonError(self)

        self.parent = parent
        self.root = parent.root

        if parent is not self:
            parent.registerChild(self)
            self.fire(Registered(self, self.parent))

        self._updateRoot(parent.root)

        return self

    @handler('unregister')
    def _on_unregister(self, component):
        if component is not self:
            return
        return self.unregister()

    def unregister(self):
        if self.unregister_pending or self.parent == self:
            return self
        # tick shouldn't be called anymore, although component is still in tree
        self._unregister_pending = True
        self.root._cache.clear()
        self.root._ticks = self.root.getTicks()
        # Give components a chance to prepare for unregister
        evt = PrepareUnregister(self)
        evt.complete_channels = (self,)
        self.fire(evt)
        return self

    @property
    def unregister_pending(self):
        return getattr(self, "_unregister_pending", False)

    @handler("prepare_unregister_complete")
    def _on_prepare_unregister_complete(self, e, value):
        # Remove component from tree now
        delattr(self, "_unregister_pending")
        self.fire(Unregistered(self, self.parent))

        if self.parent is not self:
            self.parent.unregisterChild(self)
            self.parent = self

        self._updateRoot(self)
        return self

    def _updateRoot(self, root):
        self.root = root
        for c in self.components:
            c._updateRoot(root)

Component = HandlerMetaClass("Component", (BaseComponent,), {})
"""
If you use Component instead of BaseComponent as base class for your own
component class, then all methods that are not marked as private
(i.e: start with an underscore) are automatically decorated as handlers.

The methods are invoked for all events from the component's channel
where the event's name matches the method's name.
"""
