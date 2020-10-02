#!/bin/bash

#$ -l tmem=8G
#$ -l gpu=true
#$ -pe gpu 4
#$ -R y
#$ -l h_rt=16:00:00
#$ -j y
#$ -N 'multiscale_models_g_2.5x'

 
source /share/apps/source_files/python/python-3.7.0.source
source /share/apps/source_files/cuda/cuda-10.1.source
export LD_LIBRARY_PATH=/share/apps/TensorRT-5.1.5.0/lib:$LD_LIBRARY_PATH
python3 /home/verghese/breastcancer_ln_deeplearning/scripts/python/tuning.py -rp /SAN/colcc/WSI_LymphNodes_BreastCancer/Greg/data/patches/segmentation/2.5x/one/tfrecords -rd tfrecords_g_256_32 -cf /home/verghese/breastcancer_ln_deeplearning/scripts/config/config_germinal_template_2.json -cp checkpoints -op /home/verghese/breastcancer_ln_deeplearning/output/ -mn multiscale
