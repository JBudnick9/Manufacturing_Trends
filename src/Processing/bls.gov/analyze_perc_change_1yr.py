import pandas as pd
from pathlib import Path
import os


script_dir = Path(__file__).parent.resolve()
fn = (script_dir / '../../../data/bls.gov/employment/raw/01.csv').resolve()
df = pd.read_csv(fn, delimiter='\t')
fn_out = (script_dir / '../../../data/bls.gov/employment/processed/01_1yr_perc_change.csv')
dir_processed, tail = os.path.split(fn_out)
os.makedirs(dir_processed, exist_ok=True)


percent_change_array = []
area_set = set(df.area)
for _area in area_set:
    sub_set = df[df.area == _area]
    min_year = sub_set.year.min()
    max_year = sub_set.year.max()


    year_spans = []
    for year in range(min_year, max_year-1):
        year_spans += [[year, year+1]]


    print(year_spans)

    for span in year_spans:
        state = sub_set.iloc[1].state
        area = _area
        new_year = span[1]
        old_year = span[0]

        new_number = sub_set[sub_set.year == new_year].iloc[0].value
        old_number = sub_set[sub_set.year == old_year].iloc[0].value
        
        perc_change = (new_number - old_number) / old_number
        #print('-'*13)
        #print(state, area)
        #print(new_year, old_year)
        #print(new_number, old_number, perc_change)

        percent_change_array.append([state, area, old_year, new_year, old_number, new_number, perc_change])


new_df = pd.DataFrame(percent_change_array)
new_df.columns = ['state', 'area', 'old_year', 'new_year', 'old_number', 'new_number', 'perc_change']
print(new_df.head())
print(new_df.shape)
new_df.to_csv(fn_out)
    #print(_state, sub_set.shape)