# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.python.logger._filter}.
"""

from zope.interface.verify import verifyObject, BrokenMethodImplementation

from twisted.trial import unittest

from twisted.python.logger._levels import InvalidLogLevelError
from twisted.python.logger._levels import LogLevel
from twisted.python.logger._observer import ILogObserver
from twisted.python.logger._observer import LogPublisher
from twisted.python.logger._filter import FilteringLogObserver
from twisted.python.logger._filter import PredicateResult
from twisted.python.logger._filter import LogLevelFilterPredicate



class FilteringLogObserverTests(unittest.TestCase):
    """
    Tests for L{FilteringLogObserver}.
    """

    def test_interface(self):
        """
        L{FilteringLogObserver} is an L{ILogObserver}.
        """
        observer = FilteringLogObserver(lambda e: None, ())
        try:
            verifyObject(ILogObserver, observer)
        except BrokenMethodImplementation as e:
            self.fail(e)


    def filterWith(self, *filters):
        events = [
            dict(count=0),
            dict(count=1),
            dict(count=2),
            dict(count=3),
        ]

        class Filters(object):
            @staticmethod
            def twoMinus(event):
                if event["count"] <= 2:
                    return PredicateResult.yes
                return PredicateResult.maybe

            @staticmethod
            def twoPlus(event):
                if event["count"] >= 2:
                    return PredicateResult.yes
                return PredicateResult.maybe

            @staticmethod
            def notTwo(event):
                if event["count"] == 2:
                    return PredicateResult.no
                return PredicateResult.maybe

            @staticmethod
            def no(event):
                return PredicateResult.no

            @staticmethod
            def bogus(event):
                return None

        predicates = (getattr(Filters, f) for f in filters)
        eventsSeen = []
        trackingObserver = lambda e: eventsSeen.append(e)
        filteringObserver = FilteringLogObserver(trackingObserver, predicates)
        for e in events:
            filteringObserver(e)

        return [e["count"] for e in eventsSeen]


    def test_shouldLogEvent_noFilters(self):
        """
        No filters: all events come through.
        """
        self.assertEquals(self.filterWith(), [0, 1, 2, 3])


    def test_shouldLogEvent_noFilter(self):
        """
        Filter with negative predicate result.
        """
        self.assertEquals(self.filterWith("notTwo"), [0, 1, 3])


    def test_shouldLogEvent_yesFilter(self):
        """
        Filter with positive predicate result.
        """
        self.assertEquals(self.filterWith("twoPlus"), [0, 1, 2, 3])


    def test_shouldLogEvent_yesNoFilter(self):
        """
        Series of filters with positive and negative predicate results.
        """
        self.assertEquals(self.filterWith("twoPlus", "no"), [2, 3])


    def test_shouldLogEvent_yesYesNoFilter(self):
        """
        Series of filters with positive, positive and negative predicate
        results.
        """
        self.assertEquals(self.filterWith("twoPlus", "twoMinus", "no"),
                          [0, 1, 2, 3])


    def test_shouldLogEvent_badPredicateResult(self):
        """
        Filter with invalid predicate result.
        """
        self.assertRaises(TypeError, self.filterWith, "bogus")


    def test_call(self):
        """
        Test filtering results from each predicate type.
        """
        e = dict(obj=object())

        def callWithPredicateResult(result):
            seen = []
            observer = FilteringLogObserver(lambda e: seen.append(e),
                                            (lambda e: result,))
            observer(e)
            return seen

        self.assertIn(e, callWithPredicateResult(PredicateResult.yes))
        self.assertIn(e, callWithPredicateResult(PredicateResult.maybe))
        self.assertNotIn(e, callWithPredicateResult(PredicateResult.no))


    def test_trace(self):
        """
        Tracing keeps track of forwarding through the filtering observer.
        """
        event = dict(log_trace=[])

        oYes = lambda e: None
        oNo = lambda e: None

        def testObserver(e):
            self.assertIdentical(e, event)
            self.assertEquals(
                event["log_trace"],
                [
                    (publisher, yesFilter),
                    (yesFilter, oYes),
                    (publisher, noFilter),
                    # noFilter doesn't call oNo
                    (publisher, oTest),
                ]
            )
        oTest = testObserver

        yesFilter = FilteringLogObserver(
            oYes,
            (lambda e: PredicateResult.yes,)
        )
        noFilter = FilteringLogObserver(
            oNo,
            (lambda e: PredicateResult.no,)
        )

        publisher = LogPublisher(yesFilter, noFilter, testObserver)
        publisher(event)



class LogLevelFilterPredicateTests(unittest.TestCase):
    def test_defaultLogLevel(self):
        """
        Default log level is used.
        """
        predicate = LogLevelFilterPredicate()

        self.assertEquals(
            predicate.logLevelForNamespace(None),
            LogLevelFilterPredicate.defaultLogLevel
        )
        self.assertEquals(
            predicate.logLevelForNamespace(""),
            LogLevelFilterPredicate.defaultLogLevel
        )
        self.assertEquals(
            predicate.logLevelForNamespace("rocker.cool.namespace"),
            LogLevelFilterPredicate.defaultLogLevel
        )


    def test_setLogLevel(self):
        """
        Setting and retrieving log levels.
        """
        predicate = LogLevelFilterPredicate()

        predicate.setLogLevelForNamespace(None, LogLevel.error)
        predicate.setLogLevelForNamespace("twext.web2", LogLevel.debug)
        predicate.setLogLevelForNamespace("twext.web2.dav", LogLevel.warn)

        self.assertEquals(
            predicate.logLevelForNamespace(None),
            LogLevel.error
        )
        self.assertEquals(
            predicate.logLevelForNamespace("twisted"),
            LogLevel.error
        )
        self.assertEquals(
            predicate.logLevelForNamespace("twext.web2"),
            LogLevel.debug
        )
        self.assertEquals(
            predicate.logLevelForNamespace("twext.web2.dav"),
            LogLevel.warn
        )
        self.assertEquals(
            predicate.logLevelForNamespace("twext.web2.dav.test"),
            LogLevel.warn
        )
        self.assertEquals(
            predicate.logLevelForNamespace("twext.web2.dav.test1.test2"),
            LogLevel.warn
        )


    def test_setInvalidLogLevel(self):
        """
        Can't pass invalid log levels to C{setLogLevelForNamespace()}.
        """
        predicate = LogLevelFilterPredicate()

        self.assertRaises(
            InvalidLogLevelError,
            predicate.setLogLevelForNamespace, "twext.web2", object()
        )

        # Level must be a constant, not the name of a constant
        self.assertRaises(
            InvalidLogLevelError,
            predicate.setLogLevelForNamespace, "twext.web2", "debug"
        )


    def test_clearLogLevels(self):
        """
        Clearing log levels.
        """
        predicate = LogLevelFilterPredicate()

        predicate.setLogLevelForNamespace("twext.web2", LogLevel.debug)
        predicate.setLogLevelForNamespace("twext.web2.dav", LogLevel.error)

        predicate.clearLogLevels()

        self.assertEquals(
            predicate.logLevelForNamespace("twisted"),
            LogLevelFilterPredicate.defaultLogLevel
        )
        self.assertEquals(
            predicate.logLevelForNamespace("twext.web2"),
            LogLevelFilterPredicate.defaultLogLevel
        )
        self.assertEquals(
            predicate.logLevelForNamespace("twext.web2.dav"),
            LogLevelFilterPredicate.defaultLogLevel
        )
        self.assertEquals(
            predicate.logLevelForNamespace("twext.web2.dav.test"),
            LogLevelFilterPredicate.defaultLogLevel
        )
        self.assertEquals(
            predicate.logLevelForNamespace("twext.web2.dav.test1.test2"),
            LogLevelFilterPredicate.defaultLogLevel
        )


    def test_filtering(self):
        """
        Events are filtered based on log level/namespace.
        """
        predicate = LogLevelFilterPredicate()

        predicate.setLogLevelForNamespace(None, LogLevel.error)
        predicate.setLogLevelForNamespace("twext.web2", LogLevel.debug)
        predicate.setLogLevelForNamespace("twext.web2.dav", LogLevel.warn)

        def checkPredicate(namespace, level, expectedResult):
            event = dict(log_namespace=namespace, log_level=level)
            self.assertEquals(expectedResult, predicate(event))

        checkPredicate("", LogLevel.debug, PredicateResult.no)
        checkPredicate("", LogLevel.error, PredicateResult.maybe)

        checkPredicate("twext.web2", LogLevel.debug, PredicateResult.maybe)
        checkPredicate("twext.web2", LogLevel.error, PredicateResult.maybe)

        checkPredicate("twext.web2.dav", LogLevel.debug, PredicateResult.no)
        checkPredicate("twext.web2.dav", LogLevel.error, PredicateResult.maybe)

        checkPredicate(None, LogLevel.critical, PredicateResult.no)
        checkPredicate("twext.web2", None, PredicateResult.no)
