#!/bin/bash

# build singularity container for mongodb
singularity build --fakeroot $PWD/mongodb/mongodb.sif $PWD/mongodb/Singularity

# set up container properly
singularity instance start --bind ./data/db:/data/db $PWD/mongodb/mongodb.sif brainlife_ezbids-mongodb
singularity run instance://brainlife_ezbids-mongodb # This seems to run mongodb in the foreground, meaning can't move on to building other containers

echo ""
echo "Finished building mongodb, now running in background"
echo ""