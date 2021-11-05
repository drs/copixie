TOTAL=$(grep '#Telomere' $1 | cut -d ' ' -f2)
LOCALIZED=$(grep -v '#' $1 | grep -v 'transient' | cut -d , -f1 | grep [0-9] | sort | uniq | wc -l)
DIRNAME=$(echo $1)
echo $DIRNAME,$TOTAL,$LOCALIZED


