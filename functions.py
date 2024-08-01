import os
from datetime import datetime
import geopandas
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from openpyxl import load_workbook

HEADER_KEYWORD = 'Region'
EXCEL_SHEET = 'Virtual Ward Data'
FILE_PREFIX = 'VW'
FILE_EXT = '.xlsx'
LOCATION_DATA_FILE = './data/subICSLocations.csv'
SHAPEFILE = './data/geodata/ICB_Shape.zip'
GEOJSON_OUTPUT = './data/geodata/ICB2023.geojson'
DATA_PATH = './data'
DOWNLOAD_URL = 'https://www.england.nhs.uk/statistics/statistical-work-areas/virtual-ward/'


def download_and_rename_files():
    with requests.Session() as session:
        response = requests.get(DOWNLOAD_URL)
        soup = BeautifulSoup(response.text, "html.parser")

        num_new_files_downloaded = 0
        total_files_downloaded = 0

        # create data directory if it does not exist
        if not os.path.exists(DATA_PATH):
            os.mkdir(DATA_PATH)

        # find the links to the Excel files
        for link in soup.select("a[href$='.xlsx']"):
            file_url = link['href']

            # skip the file download if the URL or filename contains 'Time-Series'
            if 'Time-Series' in file_url:
                continue

            # download the Excel file
            response = requests.get(file_url)
            with open("temp.xlsx", "wb") as f:
                f.write(response.content)
            try:
                # load the workbook and get the date from the first sheet
                wb = load_workbook('temp.xlsx')
                sheet = wb.get_sheet_by_name(wb.get_sheet_names()[1])
                date_in_sheet = sheet['C6'].value

                # format date into YYYYMM
                date_in_sheet = datetime.strptime(date_in_sheet, '%B %Y')

                # reformat the datetime object to the format YYYYMM
                workbook_formatted_date = date_in_sheet.strftime("%Y%m")

                # get net file name and path
                new_file_path = f"{DATA_PATH}/VW{workbook_formatted_date}.xlsx"
                if os.path.exists(new_file_path):
                    os.remove(new_file_path)
                num_new_files_downloaded += -1

                # rename the file and move to downloaded directory
                os.rename("temp.xlsx", new_file_path)

                # increment the counter after successful download and rename operation
                num_new_files_downloaded += 1
                total_files_downloaded += 1
            finally:
                wb.close()

        return num_new_files_downloaded, total_files_downloaded


def _clean_column_names(df):
    df.columns = df.columns.str[:25]  # truncates to the first 15 characters
    df.columns = df.columns.str.strip()  # remove whitespace from both ends
    df.columns = df.columns.str.lower()  # convert to lowercase
    df.columns = df.columns.str.replace(' ', '_')  # replaces spaces with underscores
    return df


def load_data():
    all_data = pd.DataFrame()

    excel_files = [f for f in os.listdir(DATA_PATH) if f.startswith(FILE_PREFIX) and f.endswith(FILE_EXT)]
    # Iterate through the Excel files and extract the relevant data
    for file in excel_files:
        file_path = os.path.join(DATA_PATH, file)
        file_date = file.split(FILE_PREFIX)[1].split(FILE_EXT)[0]
        df = pd.read_excel(file_path, sheet_name=EXCEL_SHEET)

        # find the index of the row that contains the keyword
        header_index = df[df.apply(lambda row: row.astype(str).str.contains(HEADER_KEYWORD).any(), axis=1)].index[0]

        # get the required table data
        table_data = df.iloc[header_index:].copy()
        table_data.columns = table_data.iloc[0]
        table_data = table_data[1:]
        table_data.rename_axis('Index', axis=1, inplace=True)
        table_data['Date'] = file_date

        # clean the data of summary rows
        table_data = table_data[~(table_data == 'ENGLAND').any(axis=1)]
        table_data = table_data[~(table_data == 'ENGLAND*').any(axis=1)]

        # drop columns that are not required
        cols_to_drop = [table_data.columns[i] for i in [0, 6, 9]]
        table_data.drop(cols_to_drop, axis=1, inplace=True)

        # clean the column names to facilitate merging
        table_data = _clean_column_names(table_data)

        # append data to all_data dataframe
        all_data = pd.concat([all_data, table_data])
        all_data.dropna(axis=1, how='all', inplace=True)

    # get columns based in their index for renaming
    cols = list(all_data.columns)

    # set dtypes
    all_data = all_data.astype({
        cols[0]: 'object',
        cols[1]: 'object',
        cols[2]: 'object',
        cols[3]: 'object',
        cols[4]: 'Int64',
        cols[5]: 'Int64',
        cols[6]: 'Int64',
        cols[7]: 'object'}
    )

    # rename columns using dictionary
    rename_dict = {
        cols[0]: 'Region',
        cols[1]: 'Region_Code',
        cols[2]: 'ICB_Code',
        cols[3]: 'Name',
        cols[4]: 'Capacity',
        cols[5]: 'GP_Registered_Population',
        cols[6]: 'Occupancy',
        cols[7]: 'Date'}
    all_data.rename(columns=rename_dict, inplace=True)
    # Set date field format and correct data
    all_data['Date'] = pd.to_datetime(all_data['Date'], format='%Y%m')
    all_data['Date'] = all_data['Date'].apply(lambda date: date.replace(day=1))

    # Add 'Occupancy_Percent' with new calculated field
    all_data['Occupancy_Percent'] = all_data['Occupancy'] / all_data['Capacity'].replace(0, np.nan)

    all_data.reset_index(drop=True, inplace=True)

    return all_data


def get_vw_dataset():
    vw_data = load_data()
    # clean whitespace data
    vw_data = vw_data.apply(lambda x: x.str.strip() if x.dtype == 'object' else x)

    # merge vw_data and icb location data using temp fields for case insensitivity
    ics_data = pd.read_csv(LOCATION_DATA_FILE)

    vw_data['temp_name'] = vw_data['Name'].str.lower()
    ics_data['temp_location'] = ics_data['ICB_Name'].str.lower()
    merged_df = pd.merge(left=vw_data, right=ics_data, left_on='temp_name', right_on='temp_location', how='left')

    # remove temporary columns
    del merged_df['temp_name']
    del merged_df['temp_location']

    # group and aggregate fields
    merged_df = merged_df.groupby(['Date', 'ICB23CD']).agg({
        'Capacity': 'sum',
        'GP_Registered_Population': 'sum',
        'Occupancy': 'sum',
        'ICB23NM': 'first',
        'NHSER23NM': 'first',
    }).reset_index()

    # replace calculated fields
    merged_df['Capacity_100k'] = (
                merged_df['Capacity'] / merged_df['GP_Registered_Population'].replace(0, np.nan) * 100000).round(2)
    merged_df['Occupancy_Percent'] = (merged_df['Occupancy'] / merged_df['Capacity'].replace(0, np.nan) * 100).round(2)

    # construct ICB23NMS which has shortened Integrated Care Board to ICB
    merged_df['ICB23NMS'] = merged_df['ICB23NM'].str.slice(0, -21) + 'ICB'

    return merged_df

def convert_shape_to_json():
    shape_data = geopandas.read_file(SHAPEFILE)
    shape_data.to_crs(epsg=4326, inplace=True)
    shape_data.to_file(GEOJSON_OUTPUT, driver='GeoJSON')
    return GEOJSON_OUTPUT


def calculate_capacity_increase(df, year, month):
    # Filter data for the selected month and the month before
    selected_month_data = df[(df['Date'].dt.year == year) &
                             (df['Date'].dt.month == month)]
    if month == 1:
        prev_month_data = df[(df['Date'].dt.year == (year - 1)) &
                             (df['Date'].dt.month == 12)]
    else:
        prev_month_data = df[(df['Date'].dt.year == year) &
                             (df['Date'].dt.month == (month - 1))]

    # Calculate the total capacity for each month for each ICS
    selected_month_capacity = selected_month_data.groupby('ICB23NMS')['Capacity'].sum()
    prev_month_capacity = prev_month_data.groupby('ICB23NMS')['Capacity'].sum()

    # Calculate the difference in capacity between the two months for each ICS
    capacity_increase = selected_month_capacity - prev_month_capacity

    # Compute previous, current, and the difference in a DataFrame
    capacity_df = pd.DataFrame({
        'Previous Capacity': prev_month_capacity,
        'Current Capacity': selected_month_capacity,
        'Increase': capacity_increase
    })

    # Only retain the top 5 increased ICSs
    top_ics_df = capacity_df.nlargest(5, 'Increase')

    return top_ics_df