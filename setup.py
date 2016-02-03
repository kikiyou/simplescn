#! /usr/bin/env python3
#license: bsd3, see LICENSE.txt

from setuptools import setup

relaxed = False
forcegui = True
#, Distribution
#from pkg_resources import Environment, working_set

#import os
#, working_set

#distributions, errors = working_set.find_plugins(Environment("plugins"))
#map(working_set.add, distributions)  # add plugins+libs to sys.path
#if len(errors)>0:
#    print("Error loading plugins: ", errors)
#print(distributions)


entry_points = {}
install_requirements = ["cryptography>=1.1"]
if forcegui:
    entry_points["gui_scripts"] = ['simplescns = simplescn.__main__:init_method_main']
    install_requirements += ["simplescn[gtkgui]", "simplescn[mdhelp]"]
elif not relaxed:
    entry_points["console_scripts"] = ['simplescns = simplescn.__main__:init_method_main']
    install_requirements += ["simplescn[mdhelp]"]
else:
    entry_points["console_scripts"] = ['simplescns = simplescn.__main__:init_method_main']

# plugins imported by MANIFEST.in
setup(name='simplescn',
      version='0.1',
      description='Simple communication nodes',
      author='Alexander K.',
      author_email='devkral@web.de',
      url='https://github.com/devkral/simplescn',
      entry_points=entry_points,
      #zip_safe=True,
      platforms='Platform Independent',
      include_package_data=True,
      package_data={
          'simplescn': ['*.txt', '*.md', 'guigtk/*.ui', 'guigtk/*.svg', 'guigtk/*.py', 'static/*', 'html/*/*.html'],
      },
      install_requires=install_requirements,
      extras_require={
          'gtkgui': ["pygobject>=3.16"],
          'mdhelp': ["markdown>=2.0"],
      },
      packages=['simplescn'],
      #ext_modules=distributions,
      license="BSD3",
      test_suite="tests")
