from nepse import Nepse
import pandas as pd

try:
    nepse = Nepse()
    nepse.setTLSVerification(False)
    
    print("Testing getDailyNepseIndexGraph...")
    data = nepse.getDailyNepseIndexGraph()
    print(f"Type: {type(data)}")
    if data:
        print(f"Length: {len(data)}")
        print(f"First item: {data[0]}")
        
    print("\nTesting getNepseIndex...")
    data2 = nepse.getNepseIndex()
    print(f"Type: {type(data2)}")
    if data2:
        print(f"Length: {len(data2)}")
        print(f"First item: {data2[0]}")

except Exception as e:
    print(f"Error: {e}")
