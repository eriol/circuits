import pytest


from time import sleep


import resource


from circuits import Event, Component


class test(Event):
    """test Event"""


class test_call(Event):
    """test Event"""


class App(Component):

    def test(self):
        return 'Hello World!'

    def test_call(self):
        for _ in range(10):
            yield self.call(test())

    @property
    def memory(self):
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


@pytest.fixture
def app(request):
    app = App()

    def finalizer():
        app.stop()

    request.addfinalizer(finalizer)
    app.start()
    return app


def test_memory_call(app):
    start_memory = app.memory

    event = test_call()

    x = app.call(event)

    while True:
        try:
            next(x)
        except StopIteration:
            break

    while app._queue or app._tasks:
        sleep(0.1)

    delta = app.memory - start_memory
    assert delta == 0


def test_memory_wait(app):
    start_memory = app.memory

    app.fire(test())

    x = app.wait("test")

    while True:
        try:
            next(x)
        except StopIteration:
            break

    while app._queue or app._tasks:
        sleep(0.1)

    delta = app.memory - start_memory
    assert delta == 0


def test_memory_fire(app):
    start_memory = app.memory

    for _ in range(10):
        app.fire(test())

    while app._queue or app._tasks:
        sleep(0.1)

    delta = app.memory - start_memory
    assert delta == 0
