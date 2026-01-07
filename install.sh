#!/bin/bash
# By Pytel

python_dependencies="pip-dependencies.txt"
apt_dependencies="apt-dependencies.txt"

echo -e "Installing apt dependencies..."
# Install apt dependencies
sudo apt-get update
if [ -f $apt_dependencies ]; then
    xargs sudo apt-get -y install < $apt_dependencies
else
    echo "No apt dependencies file found."
fi

echo -e "\nInstalling python dependencies..."
# Install python dependencies
if [ -f $python_dependencies ]; then 
    pip install -r $python_dependencies
else
    echo "No python dependencies file found."
fi

echo -e "Done!"