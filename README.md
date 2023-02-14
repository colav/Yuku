<center><img src="https://raw.githubusercontent.com/colav/colav.github.io/master/img/Logo.png"/></center>

# Yuku
Scienti Open Data / Yuku, god of rain in Yaqui mythology in northern Mexico.


# Description
This package allows to download Scienti open data using socrata api service.
We are downloading two datasets 
* "Investigadores Reconocidos por convocatoria"
* "Producción Grupos Investigación"

Additionally we are scrapping cvlac profiles of researches from scienti website.

# Installation

## Dependencies
* Install MongoDB
    * Debian based system: `apt-get install mongodb`
    * Redhat based system instructions [here](https://docs.mongodb.com/manual/tutorial/install-mongodb-on-red-hat/)
    * Conda: `conda install mongodb mongo-tools`

NOTE:

To start mongodb server on conda please run the next steps

`
mkdir -p $HOME/data/db 
`

`
mongodb mongod --dbpath $HOME/data/db/
`

## Package
`pip install yuku`

# Usage


# License
BSD-3-Clause License 

# Links
http://colav.udea.edu.co/



