#!/usr/bin/env python3
from setuptools import setup

PLUGIN_ENTRY_POINT = 'ovos-PHAL-plugin-sj201-leds=ovos_PHAL_plugin_sj201_led:MycroftSJ201'
setup(
    name='ovos-PHAL-plugin-sj201-leds',
    version='0.0.1a1',
    description='A PHAL plugin for ovos',
    url='https://github.com/OpenVoiceOS/ovos-PHAL-plugin-sj201-leds',
    author='JarbasAi',
    author_email='jarbasai@mailfence.com',
    license='Apache-2.0',
    packages=['ovos_PHAL_plugin_sj201_led'],
    install_requires=["ovos-plugin-manager>=0.0.24", "neopixel"],
    zip_safe=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Text Processing :: Linguistic',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    entry_points={'ovos.plugin.phal': PLUGIN_ENTRY_POINT}
)
