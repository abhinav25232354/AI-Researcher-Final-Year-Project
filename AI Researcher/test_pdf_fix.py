#!/usr/bin/env python3
"""
Test script to verify PDF export fix for both data types
"""

import os
import sys
from datetime import datetime

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import generate_pdf_report, CACHE

def test_pdf_export_fix():
    """Test the PDF export functionality with both data types"""
    print("Testing PDF export fix for both data types...")
    
    # Test 1: Paper list (from topic search)
    print("\n1. Testing with paper list data...")
    test_cache_id_1 = "test_papers_123"
    test_papers = [
        {
            "title": "Test Paper 1",
            "abstract": "This is a test abstract for paper 1",
            "year": 2023,
            "url": "https://example.com/paper1"
        },
        {
            "title": "Test Paper 2", 
            "abstract": "This is a test abstract for paper 2",
            "year": 2023,
            "url": "https://example.com/paper2"
        }
    ]
    
    test_processed_data_1 = {
        'summary': 'This is a comprehensive summary of the test papers.',
        'gaps': 'TITLE: Test Research Gap\nDescription: This is a test research gap description.',
        'sources': 'Found 2 papers with classifications: {\'qualitative\': 2}'
    }
    
    # Add test data to cache
    CACHE[test_cache_id_1] = test_papers
    CACHE[test_cache_id_1 + "_processed"] = test_processed_data_1
    
    try:
        # Test PDF generation for paper list
        filepath, filename = generate_pdf_report(test_cache_id_1, "Test Paper Analysis Report")
        
        if filepath and os.path.exists(filepath):
            print(f"✅ Paper list PDF export successful!")
            print(f"   File: {filename}")
            print(f"   Size: {os.path.getsize(filepath)} bytes")
            
            # Clean up test file
            os.remove(filepath)
            print("   Test file cleaned up.")
        else:
            print(f"❌ Paper list PDF export failed: {filename}")
            return False
            
    except Exception as e:
        print(f"❌ Error during paper list PDF export test: {str(e)}")
        return False
    
    # Clean up test data
    del CACHE[test_cache_id_1]
    del CACHE[test_cache_id_1 + "_processed"]
    
    # Test 2: PDF upload data
    print("\n2. Testing with PDF upload data...")
    test_cache_id_2 = "test_pdf_456"
    test_pdf_data = {
        'type': 'pdf',
        'filename': 'test_research_paper.pdf',
        'text': 'This is a test research paper content.',
        'title': 'Test Research Paper'
    }
    
    test_processed_data_2 = {
        'summary': 'This is a comprehensive summary of the test PDF.',
        'gaps': 'TITLE: Test PDF Gap\nDescription: This is a test gap from PDF.',
        'sources': '1. Test Reference 1\n2. Test Reference 2'
    }
    
    # Add test data to cache
    CACHE[test_cache_id_2] = test_pdf_data
    CACHE[test_cache_id_2 + "_processed"] = test_processed_data_2
    
    try:
        # Test PDF generation for PDF upload
        filepath, filename = generate_pdf_report(test_cache_id_2, "Test PDF Analysis Report")
        
        if filepath and os.path.exists(filepath):
            print(f"✅ PDF upload PDF export successful!")
            print(f"   File: {filename}")
            print(f"   Size: {os.path.getsize(filepath)} bytes")
            
            # Clean up test file
            os.remove(filepath)
            print("   Test file cleaned up.")
        else:
            print(f"❌ PDF upload PDF export failed: {filename}")
            return False
            
    except Exception as e:
        print(f"❌ Error during PDF upload PDF export test: {str(e)}")
        return False
    
    # Clean up test data
    del CACHE[test_cache_id_2]
    del CACHE[test_cache_id_2 + "_processed"]
    
    print("\n✅ All PDF export tests completed successfully!")
    return True

if __name__ == "__main__":
    success = test_pdf_export_fix()
    sys.exit(0 if success else 1) 