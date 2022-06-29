# -*- coding: utf-8 -*-

# -- stdlib --
import argparse

# -- third party --
# -- own --

# -- code --
class OptionsProxy(object):
    def _set_options(self, obj):
        self.obj = obj

    def __getattr__(self, attr):
        return getattr(self.obj, attr)


options = OptionsProxy()


parser = argparse.ArgumentParser('taichi-release-tests-runner')
parser.add_argument('timelines')
parser.add_argument('--log', default='INFO')


def parse_args():
    rst = parser.parse_args()
    options._set_options(rst)
