from typing import Tuple, List
import logging 
import requests
import time
import numpy as np
import pandas as pd
import datetime
import matplotlib.pyplot as plt

############### Software power meter = perf ##################

def get_perf_df(start_time, file="/tmp/result_ep.csv"):
    """Plots the evolution of the power as provided by perf.
    
    Expected use of perf:
    sudo perf stat -A -a -e 'power/energy-ram/' -e 'power/energy-pkg/' -o /tmp/result_ep.csv -x ";" -I 100
    
    The last argument -I is the time interval between measurements, in milliseconds.
    
    The fields are in this order:
       •   optional usec time stamp in fractions of second (with -I xxx)
       •   optional CPU, core, or socket identifier
       •   optional number of logical CPUs aggregated
       •   counter value
       •   unit of the counter value or empty
       •   event name
       •   run time of counter
       •   percentage of measurement time the counter was running
       •   optional variance if multiple values are collected with -r
       •   optional metric value
       •   optional unit of metric
       Additional metrics may be printed with all earlier fields being
       empty.
    
    args:
        file: str. Path to csv file provided by perf.
    """
    perf_df = pd.read_csv(file, sep=";", skiprows=1, names=["time_since_start_sec", "socket", "energy_since_last_mesure_Joules","unit", "event_name", "runtime_counter", "perc_measurement_time", "nth", "nth2"])
    perf_df = perf_df.drop(columns=["nth", "nth2"])
    
    perf_df["timestamp"]=start_time+perf_df["time_since_start_sec"] # précis à une seconde du coup
    
    perf_df["power_watt"]=perf_df["energy_since_last_mesure_Joules"]/0.1
    perf_df["power_event"]=perf_df["event_name"].apply(lambda row: row.split('/')[-2].split("-")[-1])
    
    return perf_df   

############### Physical power meter ##################

def merge_dict_with_identical_keys(dicts):
    new_dict = {}
    for key in dicts[0].keys():
        new_dict[key]=[]
        for dico in dicts:
            if type(dico[key])==list:
                new_dict[key] = new_dict[key] + dico[key]
            else:
                new_dict[key].append(dico[key])
    return new_dict  
    
def convert_energy_joule_in_kWh(energy_joule: float) -> float:
    """Converts joule in kWh"""
    return energy_joule/3600*10**(-3)

def convert_energy_kWh_in_joules(energy_kWh: float) -> float:
    """Converts kWh in Joules"""
    return energy_kWh*3600*10**(3)


def compute_time_serie_energy_joule(serie, interval) -> float:
    """Returns total energy in Joule. 
    
    args:
        serie: List. Time serie of power values in watt
        interval: float. Time interval in seconds
    """
    return np.sum(serie * interval) # in Joule


def convert_timestamps_msec(timestamp_str, format_date='%Y-%m-%dT%H:%M:%S') -> Tuple[str, str]:
    element = datetime.datetime.strptime(timestamp_str,format_date)
    timestamp = datetime.datetime.timestamp(element)
    return timestamp


class Wattmeter:

    def __init__(
        self, 
        node: str, 
        site: str, 
        start: float, 
        stop: float, 
        g5k_auth = None,
        metrics: List[str] = ["wattmetre_power_watt", "bmc_node_power_watt", "pdu_outlet_power_watt"], 
        margin=10,
        ) -> None:

        self.node = node
        self.site = site
        self.start = start
        self.stop = stop
        self.metrics = metrics
        self.g5k_auth = g5k_auth
        self.plot_start, self.plot_stop = self.convert_timestamps_string(margin=margin)
        self.energy_start, self.energy_stop = self.convert_timestamps_string(add="+02:00")
        self.results = {}
        raw_data = self.retrieve_power()
        for metric in metrics:
            self.results[metric]={}
            self.results[metric]['plot_data'] = self.process_power(metric, raw_data)
            self.results[metric]['data'] = self.results[metric]['plot_data'][
                (
                    self.results[metric]['plot_data']['timestamp'] < self.energy_stop
                )&(
                    self.results[metric]['plot_data']['timestamp'] > self.energy_start
                )
            ]
            self.results[metric]['energy_joule'] = compute_time_serie_energy_joule(
                self.results[metric]['data'][metric].values, 1)
            self.results[metric]['energy_kWh'] = convert_energy_joule_in_kWh(self.results[metric]['energy_joule'])
    
    def convert_timestamps_string(self, margin=0, add="") -> Tuple[str, str]:
        format_date='%Y-%m-%dT%H:%M:%S'+add
        request_start = time.strftime(format_date, time.localtime(self.start - margin))
        request_stop = time.strftime(format_date, time.localtime(self.stop + margin))
        return request_start, request_stop

    def retrieve_power(self) -> List[dict]:
        """
        one dictionnary for every power data point. One data point every seconds.
        returns list of dictionnaries.
        """
        url = "https://api.grid5000.fr/stable/sites/%s/metrics?metrics=%s&nodes=%s&start_time=%s&end_time=%s" \
                % (self.site, ','.join(self.metrics), self.node, self.plot_start, self.plot_stop)
        print("URL de la requête wattmètre: ", url)
        logging.info(url)
        if self.g5k_auth is not None:
            return requests.get(url, auth=self.g5k_auth, verify=False).json()  # 
        else:
            return requests.get(url, verify=False).json() 


    def process_power(self, metric: str, raw_data: dict) -> pd.DataFrame:
        """
        Converts list of dict to dataframe 
        
        Format of raw data: List of dict:
            {
            'timestamp': '2022-02-25T09:02:15.40325+01:00', 
            'device_id': 'chifflet-7', 
            'metric_id': 'bmc_node_power_watt', 
            'value': 196, 
            'labels': {}
            }
        
        returns:
            df with columns "timestamp", "value"
        """
        timestamps = np.array([d['timestamp'] for d in raw_data if d['metric_id']==metric])
        timestamp_ms = []
        for timestamp_str in timestamps:
            res = convert_timestamps_msec(timestamp_str, format_date='%Y-%m-%dT%H:%M:%S+02:00')
            timestamp_ms.append(res)
        values = np.array([d['value'] for d in raw_data if d['metric_id']==metric])
        dict_for_df = {'timestamp': timestamps,'timestamp_ms': timestamp_ms, metric:values}
        return pd.DataFrame(dict_for_df)


############### Sort ##################


def qsort(tab):
    def split(tab, first_idx, last_idx, pivot_idx):
        tab[pivot_idx], tab[last_idx] = tab[last_idx], tab[pivot_idx]
        j = first_idx
        for i in range(first_idx, last_idx):
            if tab[i] <= tab[last_idx]:
                tab[i], tab[j] = tab[j], tab[i]
                j += 1
        tab[last_idx], tab[j] = tab[j], tab[last_idx]
        return j

    def quick_sort(tab, first_idx, last_idx):
        if first_idx < last_idx:
            pivot_idx = first_idx
            pivot_idx = split(tab, first_idx, last_idx, pivot_idx)
            quick_sort(tab, first_idx, pivot_idx - 1)
            quick_sort(tab, pivot_idx + 1, last_idx)

    quick_sort(tab, 0, len(tab) - 1)
    
def insertion_sort(tab):
    for i in range(1, len(tab)):
        j = i
        while tab[j - 1] > tab[j] and j > 0:
            tab[j - 1], tab[j] = tab[j], tab[j - 1]
            j -= 1


############### plots ##################

           
def get_data(exp_name, results, NOEUD):
    # perf
    perf_df = get_perf_df(results[exp_name]["perf_start"], file=f"~/TP_conso/perf_results/{exp_name}.csv")
    
    origin = results[exp_name]["stress_start"]
    sec_col = "sec"
    perf_df[sec_col]=perf_df["timestamp"]-origin
    
    perf_stress_df = perf_df[
        (perf_df["timestamp"]>results[exp_name]["stress_start"])&(perf_df["timestamp"]<results[exp_name]["stress_end"])]
    perf_energy_joules = perf_stress_df["energy_since_last_mesure_Joules"].sum()
    
    # wattmètre
    watt = Wattmeter(
        NOEUD, 
        "lyon", 
        results[exp_name]["stress_start"], 
        results[exp_name]["stress_end"], 
        metrics=["wattmetre_power_watt"])
        
    watt_df = watt.results['wattmetre_power_watt']['plot_data']
    watt_df[sec_col]=watt_df["timestamp_ms"]-origin
    
    return perf_energy_joules, perf_df, watt, watt_df


def plot_timeseries(ax, perf_df, watt_df, exp_name, only_totals=False):
    
    if not only_totals:
        for label, gp in perf_df.groupby(["socket", "power_event"]):
            # print(" ".join(list(gp)))
            label = " ".join(list(label))
            gp.plot(ax=ax, x="sec", y="power_watt", label=exp_name+": "+label)

    perf_df.groupby(["sec"]).sum().plot(ax=ax, y="power_watt", label=exp_name+": "+"total CPU")

    watt_df.plot(
        ax=ax, 
        x="sec", 
        y="wattmetre_power_watt", 
        label=exp_name+": "+"Wattmètre physique"
    )
    FONTSIZE=15
    ax.set_xlabel('Timestamps (seconds)', fontsize=FONTSIZE)
    ax.set_ylabel('Power (W)', fontsize=FONTSIZE)
    ax.set_title(f'Evolution of power',
                 #y=-0.12, 
                 fontsize=FONTSIZE+5
                )

    return ax