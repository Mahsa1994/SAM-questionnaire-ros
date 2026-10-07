from glob import glob

from setuptools import setup

package_name = 'sam_questionnaire'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/web', glob('web/*.html')),
        ('share/' + package_name + '/web/img', glob('web/img/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lair',
    maintainer_email='ama.hasheminejad@gmail.com',
    description='SAM questionnaire web app publishing ratings to ROS2',
    license='MIT',
    entry_points={
        'console_scripts': [
            'sam_node = sam_questionnaire.sam_node:main',
        ],
    },
)
