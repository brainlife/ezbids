#!/bin/bash

# build singularity container for mongodb
singularity build --fakeroot $PWD/mongodb.sif Singularity

# set up container properly
singularity instance start --bind ../data/db:/data/db mongodb.sif brainlife_ezbids-mongodb
singularity run instance://brainlife_ezbids-mongodb

echo ""
echo "Finished building mongodb, now running in background"
echo ""