
import requests
import pandas as pd
import pickle
import time
import os


class StateEmployment:
    def __init__(self, filename='output.csv'):
        self.base_url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
        self.apikey = os.environ.get('BLS_API_KEY')
        self.states = pd.read_csv('sm.state.txt', delimiter='\t')
        self.area_codes = pd.read_csv('sm.area.txt', delimiter='\t')
        self.industries = pd.read_csv('sm.industry.txt', delimiter='\t')
        self.fn = filename
        self._us_states = {
            "AL": "Alabama",
            "AK": "Alaska",
            "AZ": "Arizona",
            "AR": "Arkansas",
            "CA": "California",
            "CO": "Colorado",
            "CT": "Connecticut",
            "DE": "Delaware",
            "FL": "Florida",
            "GA": "Georgia",
            "HI": "Hawaii",
            "ID": "Idaho",
            "IL": "Illinois",
            "IN": "Indiana",
            "IA": "Iowa",
            "KS": "Kansas",
            "KY": "Kentucky",
            "LA": "Louisiana",
            "ME": "Maine",
            "MD": "Maryland",
            "MA": "Massachusetts",
            "MI": "Michigan",
            "MN": "Minnesota",
            "MS": "Mississippi",
            "MO": "Missouri",
            "MT": "Montana",
            "NE": "Nebraska",
            "NV": "Nevada",
            "NH": "New Hampshire",
            "NJ": "New Jersey",
            "NM": "New Mexico",
            "NY": "New York",
            "NC": "North Carolina",
            "ND": "North Dakota",
            "OH": "Ohio",
            "OK": "Oklahoma",
            "OR": "Oregon",
            "PA": "Pennsylvania",
            "RI": "Rhode Island",
            "SC": "South Carolina",
            "SD": "South Dakota",
            "TN": "Tennessee",
            "TX": "Texas",
            "UT": "Utah",
            "VT": "Vermont",
            "VA": "Virginia",
            "WA": "Washington",
            "WV": "West Virginia",
            "WI": "Wisconsin",
            "WY": "Wyoming",
            "DC": "District of Columbia",
            "PR": "Puerto Rico",
            "VI": "Virgin Islands",
            "GU": "Guam",
            "AS": "American Samoa",
            "MP": "Northern Mariana Islands"
        }

    def fetch_data(self, series_ids: list, endyear=2026):
        headers = {'Content-type': 'application/json'}
        payload = {
            "seriesid": series_ids,
            "registrationkey": self.apikey,
            "startyear": str(endyear-19),
            "endyear": str(endyear)
        }

        try:
            r = requests.post(self.base_url, json=payload, headers=headers)
            r.raise_for_status()  # Raises exception for 4xx/5xx status codes
            return r.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error: {e}")
        except requests.exceptions.ConnectionError:
            print("Connection failed - check your internet")
        except requests.exceptions.Timeout:
            print("Request timed out")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
        
        return None

    def build_series_id(self, state_code: str, area_code: str, 
                        industry_code: str, data_type: str = "01",
                        seasonal_adj: str = "U", prefix: str = "SM") -> str:
        """
        Build a BLS series ID from components
        Format: SM + U + SS + AAAAA + IIIIIIII + DD
        """
        return f"{prefix}{seasonal_adj}{state_code:0>2}{area_code:0>5}{industry_code:0>8}{data_type:0>2}"

    def get_statecode_from_area(self, area_name: str) -> str:
        state_abrv = ''
        parts = area_name.split(', ')
        #  print(parts)
        state_abrv = parts[1].replace(' ','-').split('-')[0]

        state = self._us_states[state_abrv]

        return int(self.states[self.states['state_name']==state]['state_code'].iloc[0])

    def get_industry_code(self, keyword: str) -> list:
        """Find industry codes matching a keyword"""
        mask = self.industries['industry_name'].str.contains(keyword, case=False, na=False)
        return self.industries[mask][['industry_code', 'industry_name']].values.tolist()

    def make_series(self, keyword: str = "Manufacturing", data_type:str = '01') -> list:
        """Generate series IDs for all states for a given industry"""
        series_ids = []
        
        # Find matching industry codes
        matching_industries = self.get_industry_code(keyword)
        #print(f"Found industries matching '{keyword}': {matching_industries}")
        
        # Pick the main one (you might want to be more specific)
        if not matching_industries:
            print("No matching industries found")
            return []
        
        print("Matched industry: ", matching_industries[0])
        industry_code = matching_industries[0][0]  # First match
        state_code = ''
        area_code = ''
        
        for _, row in self.area_codes.iterrows():
            area_code = row.area_code
            if area_code not in [99999, 00000]:
                state_code = self.get_statecode_from_area(row.area_name)
                series_ids.append(self.build_series_id(state_code=state_code, area_code=area_code, industry_code=industry_code, data_type=data_type))

        return series_ids

    def subset_series(self, series:list, chunk_len:int=50) -> list:
        '''Turns a long list of series into chunks of 50 for the max api length'''

        length = len(series)
        groups = length//chunk_len
        chunks = []

        for i in range(0,groups+1):
            start = i * chunk_len
            end = start + chunk_len
            chunks.append(series[start:end])

        return chunks

    def download(self, series:list):
        with open(self.fn, 'w') as f:
            header = "\t".join(['series_id', 'state', 'area', 'year', 'period', 'month', 'value'])                                    
            f.write(header + '\n')

        # this will need to call each series in groups of 50 and then write the data to a csv file
        unique_series = list(set(series))
        for chunk in self.subset_series(unique_series, 50):
            j = self.fetch_data(chunk)
            if j is None:
                print("Skipping chunk due to fetch error")
                continue

            self.save_data(j)

            time.sleep(.3)
        
    
    def save_data(self, json):
        if json is None:
            print("Skipping: No data returned")
            return
            
        if 'Results' not in json:
            print(f"API error: {json.get('message', 'Unknown error')}")
            return

        results = json['Results']

        try:
            series_list = results['series']
        except KeyError:
            print('API issue, likely hit rate limit.')
            return 

        with open(self.fn, 'a') as f:
            for series in results['series']:
                series_id = series['seriesID']
                data = series['data']
                state, area = self.extract_area_from_series_id(series_id)

                for item in data:
                    year = item['year']
                    period = item['period']
                    month = item['periodName']
                    value = item['value']

                    f.write("\t".join([series_id, state, area, year, period, month, value]))
                    f.write('\n')
        
    def extract_area_from_series_id(self, series_id):
        state_code = series_id[3:5]
        area_code = series_id[5:10]

        state = self.states[self.states['state_code']==int(state_code)].iloc[0]['state_name']
        area = self.area_codes[self.area_codes['area_code']==int(area_code)].iloc[0]['area_name']

        return state, area



if __name__ == '__main__':
    DATA_OUT_DIR = "../../../../data/bls.gov/employment"
    os.makedirs(DATA_OUT_DIR, exist_ok=True)
    data_types = ['01', '03', '06', '07', '08', '30']

    for dt in data_types:
        fn = os.path.join(DATA_OUT_DIR, dt+'.csv')
        s = StateEmployment(filename=fn)
        series = s.make_series(data_type=dt)
        print("Total series:",len(series))
        s.download(series)
        print("Done scraping datatype:", dt)


