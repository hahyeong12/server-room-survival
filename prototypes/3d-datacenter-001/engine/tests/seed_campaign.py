"""DEVELOPMENT AID ONLY (not used by the final QA run): play the regular campaign 1 -> 5 through the adapter's
real actions into a given (temporary) save folder, so browser failure checks can be iterated quickly from its
chapter-start points. The final Phase 5 QA plays the whole campaign through the browser UI instead.

    python -m engine.tests.seed_campaign <temporary save dir>
"""
import sys
import unittest

from engine.adapter import GameHost
from engine.tests.test_campaign import Driver


class _Shim(unittest.TestCase):
    def runTest(self):
        pass

    def act(self, game, **action):
        try:
            return {'ok': True, **game.act(action)}
        except ValueError as exc:
            return {'ok': False, 'message': str(exc)}


def main(folder):
    host = GameHost(folder)
    try:
        game = host.new_game('story')
        d = Driver(_Shim(), game)
        d.chapter1(); d.next_chapter('2'); d.chapter2_success(); d.next_chapter('3'); d.chapter3_success()
        d.next_chapter('3b'); d.chapter3b_success(); d.next_chapter('lab'); d.chapter5()
        print(game.id)
    finally:
        host.close()


if __name__ == '__main__':
    main(sys.argv[1])
