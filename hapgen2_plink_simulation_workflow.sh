#!/bin/bash

# Based off of https://github.com/HannahVMeyer/PhenotypeSimulator/blob/master/vignettes/Simulation-and-LinearModel.Rmd

# set directory variables
dir=~/code/polygenic_lasso/data
hapdir=$dir/ALL_1000G_phase1integrated_v3_impute


# move to correct directory (hap, legend, and map files should already be in directory)
cd $hapdir


# cuts the first 5k SNPs from each chromosome that exist across both .legend and genetic map files for the chromosome, with MAF >= 0.01
python3 IMPUTEfiles_prune5k.py


# generate simulated data in oxford format using resampling
# have to experimentally change 'x'p in dummy var in case of "no suitable disease loci"
# edit -n flag to change num of individuals simulated
for chr in `seq 1 22`; do
    dummyDL=`sed -n '210'p $hapdir/ALL_1000G_phase1integrated_v3_chr${chr}_impute_pruned.legend | cut -d ' '  -f 2`
    hapgen2 -m $hapdir/genetic_map_chr${chr}_combined_b37_pruned.txt -l $hapdir/ALL_1000G_phase1integrated_v3_chr${chr}_impute_pruned.legend -h $hapdir/chr${chr}.ceu_subset_pruned.hap -o $hapdir/genotypes_chr${chr}_hapgen -n 10000 0 -dl $dummyDL 0 0 0 -no_haps_output; done
    

# new version
# convert to plink format and prune SNPs 
# check .fam files have correct number of individuals (2kb ~= 100 people for .fam)
> file_list
for chr in `seq 1 22`; do
	plink --data genotypes_chr${chr}_hapgen.controls --oxford-single-chr $chr --maf 0.01 --make-bed --out genotypes_chr${chr}_hapgen.controls
	
	plink --bfile genotypes_chr${chr}_hapgen.controls --indep-pairwise 50kb 5 .99 --out genotypes_chr${chr}_hapgen.controls

	plink --bfile genotypes_chr${chr}_hapgen.controls --extract genotypes_chr${chr}_hapgen.controls.prune.in --make-bed --out genotypes_chr${chr}_hapgen.controls

	echo -e "genotypes_chr${chr}_hapgen.controls" >> file_list
done


# Merge chromsome-wide files into a single, genome-wide file
# Should have 67k variants under current config
# --allow-no-sex is not in PhenotypeSimulator vignette, but doesn't work without; no missnp generated either
plink --merge-list file_list --make-bed --allow-no-sex --out genotypes_genome_hapgen.controls

# compute kinship
plink --bfile genotypes_genome_hapgen.controls\
        --make-rel square \
        --out genotypes_genome_hapgen.controls.grm
