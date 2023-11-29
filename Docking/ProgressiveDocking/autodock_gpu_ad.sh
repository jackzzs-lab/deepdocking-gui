#!/bin/bash
#SBATCH --job-name=autodock
#SBATCH --gres=gpu:1
#SBATCH --mem-per-gpu=0
#SBATCH --output=slurm-phase_3-%x.%j.out
#SBATCH --error=slurm-phase_3-%x.%j.err

start=`date +%s`

wg=$1                #WORK-GROUP
sa=$2                #SEARCH ALGORITHM
fl=$3                #FLD FILE
lg=$4                #LIGAND FOLDER
lt=$5                #LIST FILE
ne=$6                #NUMBER OF ENERGY EVALUATIONS
nr=$7                #NUMBER OF RUNS

ad_path=$8
scripts=$9

echo Partition: $SLURM_JOB_PARTITION

# This should activate the conda environment
source ~/.bashrc
source $scripts/activation_script.sh

rm -f list.txt *dlg *xml init*
echo "$fl">>$lt
for i in $lg'/'*pdbqt
do
    echo $i>>$lt
    tmp=$(awk -F'/' '{print $NF}'<<<$i)
    tmp=$(cut -d'.' -f1<<<$tmp)
    echo $tmp>>$lt
done
wait

$ad_path'/'autodock_gpu_"$wg"wi -lsmet $sa -filelist $lt -nrun $nr -nev $ne
wait $!

#EXTRACT SINGLE BEST POSES
dlg_fold=$(pwd)                                               #FOLDER WITH ALL DLG FILES FROM AUTODOCK
mode=lc                                                       #ANALYSIS MODE, LARGEST CLUSTER (lc) or BEST BINDING ENERGY (be)
out_fold=$dlg_fold'/'results                                  #OUTPUT FOLDER
out_file=$(echo $dlg_fold | rev | cut -d'/' -f 1 | rev)       #OUTPUT SDF FILE (NO EXTENSION)

rm -r $out_fold
mkdir $out_fold
mkdir $out_fold/pdbqt

find . -name "$dlg_fold/*dlg" -print0 | 
    while IFS= read -r -d '' line; do 
        name=$(grep -m 1 'Name' $i|awk '{print $5}')
        if [ "$mode" == "be" ]; then
        run=$(grep -m 1 'RANKING' $i|awk '{print $3}')
        score=$(grep -m 1 'RANKING' $i|awk '{print $4}')
        elif [ "$mode" == "lc" ]; then
        score=$(grep '#' $i|awk '$9>a {a=$9; b=$3} END {print b}')
        run=$(grep '#' $i|awk '$9>a {a=$9; b=$5} END {print b}')
        fi
        echo "ADSCOR   $score">>$out_fold/pdbqt/$name
        awk -v p="DOCKED: MODEL        $run" '$0~p{f=1} f{print} f&&/DOCKED: ENDMDL/{exit}' $i|cut -c9-|sed '/USER/d;/REMARK/d;/MODEL/d;/TORSDOF/d'>>$out_fold/pdbqt/$name
    done

perl -e "for(<$dlg_fold/*dlg>){((stat)[9]<(unlink))}"
perl -e "for(<$dlg_fold/*xml>){((stat)[9]<(unlink))}"

cd $out_fold/pdbqt
mkdir ../sdf
find . -type f | xargs -d '\n' -n 10000 bash -c 'obabel -ipdbqt "$@" -osdf -m;' command
find . -type f | xargs -d '\n' -n 10000 bash -c "cat \"$@\" >> ../sdf/res_$out_file'.'sdf;" command
cd ..
perl -e "for(<pdbqt/*>){((stat)[9]<(unlink))}"
rm -r pdbqt

end=`date +%s`
echo $((end-start))
echo finished
