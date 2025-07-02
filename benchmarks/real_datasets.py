"""
Real medical dataset support for benchmarking.

This module provides access to real medical datasets for comprehensive
benchmarking and validation testing.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import os

# Optional imports for web requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class RealMedicalDatasets:
    """Access to real medical datasets for benchmarking."""
    
    def __init__(self, cache_dir: str = "benchmark_data"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Dataset sources and configurations
        self.datasets = {
            "mimic_sample": {
                "url": "https://physionet.org/files/mimiciii/1.4/",
                "description": "MIMIC-III Clinical Database sample",
                "requires_auth": True,
                "size_mb": 50,
            },
            "covid19_public": {
                "url": "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/owid-covid-data.csv",
                "description": "COVID-19 public dataset",
                "requires_auth": False,
                "size_mb": 5,
            },
            "heart_disease": {
                "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/",
                "description": "Heart Disease dataset from UCI",
                "requires_auth": False,
                "size_mb": 1,
            },
            "diabetes": {
                "url": "https://www4.stat.ncsu.edu/~boos/var.select/diabetes.tab.txt",
                "description": "Diabetes dataset",
                "requires_auth": False,
                "size_mb": 1,
            }
        }
    
    def get_covid19_data(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Get COVID-19 public dataset."""
        
        cache_file = self.cache_dir / "covid19_data.csv"
        
        if not cache_file.exists():
            print("Downloading COVID-19 dataset...")
            try:
                if not REQUESTS_AVAILABLE:
                    print("Warning: requests not available. Using synthetic data.")
                    return self._generate_covid19_synthetic()
                
                url = "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/owid-covid-data.csv"
                df = pd.read_csv(url)
                df.to_csv(cache_file, index=False)
                print(f"Downloaded {len(df):,} records")
            except Exception as e:
                print(f"Failed to download COVID-19 data: {e}")
                return self._generate_covid19_synthetic()
        else:
            df = pd.read_csv(cache_file)
        
        if limit:
            df = df.head(limit)
        
        # Clean and prepare the data
        df = self._clean_covid19_data(df)
        return df
    
    def _clean_covid19_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare COVID-19 data for validation."""
        
        # Select relevant columns
        relevant_cols = [
            'date', 'location', 'total_cases', 'new_cases', 'total_deaths',
            'new_deaths', 'total_vaccinations', 'people_vaccinated',
            'population', 'life_expectancy'
        ]
        
        available_cols = [col for col in relevant_cols if col in df.columns]
        result_df = df[available_cols].copy()  # type: ignore
        
        # Convert date column
        if 'date' in result_df.columns:
            result_df['date'] = pd.to_datetime(result_df['date'], errors='coerce')
        
        # Fill missing values - use a simple approach that avoids type issues
        for col in result_df.columns:
            if col != 'date':  # Skip date column
                result_df[col] = result_df[col].fillna(0)
        
        return result_df
    
    def _generate_covid19_synthetic(self) -> pd.DataFrame:
        """Generate synthetic COVID-19 data if download fails."""
        
        print("Generating synthetic COVID-19 data...")
        
        np.random.seed(42)
        n_records = 10000
        
        countries = ['USA', 'UK', 'Germany', 'France', 'Italy', 'Spain', 'Canada', 'Australia']
        
        data = {
            'date': pd.date_range(start='2020-01-01', periods=n_records, freq='D'),
            'location': np.random.choice(countries, n_records),
            'total_cases': np.random.poisson(1000, n_records),
            'new_cases': np.random.poisson(100, n_records),
            'total_deaths': np.random.poisson(50, n_records),
            'new_deaths': np.random.poisson(5, n_records),
            'total_vaccinations': np.random.poisson(500, n_records),
            'people_vaccinated': np.random.poisson(400, n_records),
            'population': np.random.uniform(1000000, 100000000, n_records),
            'life_expectancy': np.random.normal(75, 5, n_records)
        }
        
        return pd.DataFrame(data)
    
    def get_heart_disease_data(self) -> pd.DataFrame:
        """Get Heart Disease dataset."""
        
        cache_file = self.cache_dir / "heart_disease.csv"
        
        if not cache_file.exists():
            print("Downloading Heart Disease dataset...")
            try:
                if not REQUESTS_AVAILABLE:
                    print("Warning: requests not available. Using synthetic data.")
                    return self._generate_heart_disease_synthetic()
                
                # UCI Heart Disease dataset
                url = "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data"
                df = pd.read_csv(url, header=None)
                
                # Column names for the dataset
                columns = [
                    'age', 'sex', 'cp', 'trestbps', 'chol', 'fbs', 'restecg',
                    'thalach', 'exang', 'oldpeak', 'slope', 'ca', 'thal', 'target'
                ]
                df.columns = columns
                
                df.to_csv(cache_file, index=False)
                print(f"Downloaded {len(df):,} records")
                
            except Exception as e:
                print(f"Failed to download Heart Disease data: {e}")
                return self._generate_heart_disease_synthetic()
        else:
            df = pd.read_csv(cache_file)
        
        return df
    
    def _generate_heart_disease_synthetic(self) -> pd.DataFrame:
        """Generate synthetic heart disease data."""
        
        print("Generating synthetic Heart Disease data...")
        
        np.random.seed(42)
        n_records = 5000
        
        data = {
            'age': np.random.normal(55, 10, n_records).astype(int),
            'sex': np.random.choice([0, 1], n_records),
            'cp': np.random.choice([0, 1, 2, 3], n_records),
            'trestbps': np.random.normal(130, 20, n_records).astype(int),
            'chol': np.random.normal(250, 50, n_records).astype(int),
            'fbs': np.random.choice([0, 1], n_records),
            'restecg': np.random.choice([0, 1, 2], n_records),
            'thalach': np.random.normal(150, 20, n_records).astype(int),
            'exang': np.random.choice([0, 1], n_records),
            'oldpeak': np.random.exponential(1, n_records),
            'slope': np.random.choice([0, 1, 2], n_records),
            'ca': np.random.choice([0, 1, 2, 3, 4], n_records),
            'thal': np.random.choice([0, 1, 2, 3], n_records),
            'target': np.random.choice([0, 1], n_records)
        }
        
        return pd.DataFrame(data)
    
    def get_diabetes_data(self) -> pd.DataFrame:
        """Get Diabetes dataset."""
        
        cache_file = self.cache_dir / "diabetes.csv"
        
        if not cache_file.exists():
            print("Downloading Diabetes dataset...")
            try:
                if not REQUESTS_AVAILABLE:
                    print("Warning: requests not available. Using synthetic data.")
                    return self._generate_diabetes_synthetic()
                
                url = "https://www4.stat.ncsu.edu/~boos/var.select/diabetes.tab.txt"
                df = pd.read_csv(url, sep='\t')
                df.to_csv(cache_file, index=False)
                print(f"Downloaded {len(df):,} records")
                
            except Exception as e:
                print(f"Failed to download Diabetes data: {e}")
                return self._generate_diabetes_synthetic()
        else:
            df = pd.read_csv(cache_file)
        
        return df
    
    def _generate_diabetes_synthetic(self) -> pd.DataFrame:
        """Generate synthetic diabetes data."""
        
        print("Generating synthetic Diabetes data...")
        
        np.random.seed(42)
        n_records = 3000
        
        data = {
            'age': np.random.normal(50, 15, n_records).astype(int),
            'sex': np.random.choice([1, 2], n_records),
            'bmi': np.random.normal(30, 5, n_records),
            'bp': np.random.normal(100, 15, n_records),
            's1': np.random.normal(200, 50, n_records),
            's2': np.random.normal(120, 30, n_records),
            's3': np.random.normal(50, 10, n_records),
            's4': np.random.normal(25, 5, n_records),
            's5': np.random.normal(5, 1, n_records),
            's6': np.random.normal(100, 20, n_records),
            'y': np.random.normal(150, 50, n_records)
        }
        
        return pd.DataFrame(data)
    
    def get_ehr_sample_data(self) -> pd.DataFrame:
        """Generate realistic Electronic Health Record sample data."""
        
        print("Generating realistic EHR sample data...")
        
        np.random.seed(42)
        n_records = 10000
        
        # Realistic medical data
        data = {
            'patient_id': [f"P{i:08d}" for i in range(n_records)],
            'admission_date': pd.date_range(start='2020-01-01', periods=n_records, freq='H'),
            'discharge_date': pd.date_range(start='2020-01-02', periods=n_records, freq='H'),
            'age': np.random.normal(60, 20, n_records).astype(int),
            'gender': np.random.choice(['M', 'F'], n_records),
            'race': np.random.choice(['White', 'Black', 'Hispanic', 'Asian', 'Other'], n_records),
            'primary_diagnosis': np.random.choice([
                'A01.1', 'B02.2', 'C03.3', 'D04.4', 'E05.5', 'F06.6', 'G07.7',
                'H08.8', 'I09.9', 'J10.0', 'K11.1', 'L12.2', 'M13.3', 'N14.4'
            ], n_records),
            'secondary_diagnosis': np.random.choice([
                'A01.1', 'B02.2', 'C03.3', 'D04.4', 'E05.5', 'F06.6', 'G07.7',
                'H08.8', 'I09.9', 'J10.0', 'K11.1', 'L12.2', 'M13.3', 'N14.4'
            ], n_records),
            'length_of_stay': np.random.exponential(5, n_records).astype(int),
            'total_charges': np.random.lognormal(10, 1, n_records),
            'temperature': np.random.normal(98.6, 2, n_records),
            'heart_rate': np.random.normal(80, 20, n_records),
            'blood_pressure_systolic': np.random.normal(120, 20, n_records),
            'blood_pressure_diastolic': np.random.normal(80, 10, n_records),
            'respiratory_rate': np.random.normal(16, 4, n_records),
            'oxygen_saturation': np.random.normal(98, 2, n_records),
            'glucose': np.random.normal(100, 30, n_records),
            'creatinine': np.random.exponential(1, n_records),
            'hemoglobin': np.random.normal(14, 2, n_records),
            'white_blood_cells': np.random.normal(7, 2, n_records),
            'platelets': np.random.normal(250, 50, n_records),
            'discharge_disposition': np.random.choice([
                'Home', 'SNF', 'Rehab', 'Hospice', 'Expired', 'AMA'
            ], n_records),
            'readmission_30_days': np.random.choice([0, 1], n_records, p=[0.8, 0.2])
        }
        
        # Add some realistic errors
        error_rate = 0.05  # 5% error rate
        error_indices = np.random.choice(n_records, size=int(n_records * error_rate), replace=False)
        
        for idx in error_indices:
            # Add various types of errors
            error_type = np.random.choice(['age', 'temp', 'bp', 'diagnosis', 'date'])
            
            if error_type == 'age':
                data['age'][idx] = np.random.randint(150, 200)  # Impossible age
            elif error_type == 'temp':
                data['temperature'][idx] = np.random.uniform(200, 300)  # Impossible temp
            elif error_type == 'bp':
                data['blood_pressure_systolic'][idx] = np.random.uniform(300, 500)  # Impossible BP
            elif error_type == 'diagnosis':
                data['primary_diagnosis'][idx] = 'INVALID_CODE'
            elif error_type == 'date':
                data['admission_date'][idx] = pd.Timestamp('1900-01-01')  # Invalid date
        
        return pd.DataFrame(data)
    
    def get_available_datasets(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available datasets."""
        return self.datasets.copy()
    
    def list_cached_datasets(self) -> List[str]:
        """List datasets that are already cached."""
        cached = []
        for dataset_name in self.datasets.keys():
            cache_file = self.cache_dir / f"{dataset_name}.csv"
            if cache_file.exists():
                cached.append(dataset_name)
        return cached


def create_validation_profiles_for_real_data() -> Dict[str, Dict[str, Any]]:
    """Create validation profiles specifically for real medical datasets."""
    
    return {
        "covid19": {
            "description": "COVID-19 data validation profile",
            "validators": {
                "schema": {
                    "required_columns": ["date", "location", "total_cases"],
                    "column_types": {
                        "date": "datetime",
                        "total_cases": "int",
                        "new_cases": "int",
                        "total_deaths": "int",
                        "population": "float"
                    }
                },
                "ranges": {
                    "total_cases": {"min": 0},
                    "new_cases": {"min": 0},
                    "total_deaths": {"min": 0},
                    "population": {"min": 0},
                    "life_expectancy": {"min": 0, "max": 120}
                },
                "dates": {
                    "date_columns": ["date"],
                    "min_date": "2019-12-01",
                    "max_date": "2024-12-31"
                }
            }
        },
        "ehr": {
            "description": "Electronic Health Records validation profile",
            "validators": {
                "schema": {
                    "required_columns": ["patient_id", "admission_date", "age"],
                    "column_types": {
                        "patient_id": "string",
                        "admission_date": "datetime",
                        "age": "int",
                        "temperature": "float",
                        "heart_rate": "int",
                        "total_charges": "float"
                    }
                },
                "ranges": {
                    "age": {"min": 0, "max": 120},
                    "temperature": {"min": 70, "max": 110},
                    "heart_rate": {"min": 30, "max": 250},
                    "blood_pressure_systolic": {"min": 50, "max": 300},
                    "blood_pressure_diastolic": {"min": 30, "max": 200},
                    "respiratory_rate": {"min": 5, "max": 50},
                    "oxygen_saturation": {"min": 70, "max": 100},
                    "glucose": {"min": 20, "max": 1000},
                    "creatinine": {"min": 0.1, "max": 50},
                    "hemoglobin": {"min": 5, "max": 25},
                    "white_blood_cells": {"min": 0.1, "max": 100},
                    "platelets": {"min": 10, "max": 1000}
                },
                "medical_codes": {
                    "primary_diagnosis": "icd10",
                    "secondary_diagnosis": "icd10"
                },
                "dates": {
                    "date_columns": ["admission_date", "discharge_date"],
                    "min_date": "2010-01-01",
                    "max_date": "2024-12-31"
                }
            }
        },
        "heart_disease": {
            "description": "Heart disease dataset validation profile",
            "validators": {
                "schema": {
                    "required_columns": ["age", "sex", "cp", "target"],
                    "column_types": {
                        "age": "int",
                        "sex": "int",
                        "cp": "int",
                        "trestbps": "int",
                        "chol": "int",
                        "fbs": "int",
                        "restecg": "int",
                        "thalach": "int",
                        "exang": "int",
                        "oldpeak": "float",
                        "slope": "int",
                        "ca": "int",
                        "thal": "int",
                        "target": "int"
                    }
                },
                "ranges": {
                    "age": {"min": 0, "max": 120},
                    "trestbps": {"min": 50, "max": 300},
                    "chol": {"min": 100, "max": 600},
                    "thalach": {"min": 50, "max": 250},
                    "oldpeak": {"min": 0, "max": 10}
                }
            }
        }
    } 