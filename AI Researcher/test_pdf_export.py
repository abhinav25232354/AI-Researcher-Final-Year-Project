#!/usr/bin/env python3
"""
Test script for PDF export functionality
"""

import os
import sys
from datetime import datetime

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import generate_pdf_report, CACHE

def test_pdf_export():
    """Test the PDF export functionality"""
    print("Testing PDF export functionality...")
    
    # Create test data
    test_cache_id = "test_123"
    test_data = {
        'type': 'pdf',
        'filename': 'test_research_paper.pdf',
        'text': 'This is a test research paper content.',
        'title': 'Test Research Paper'
    }
    
    test_processed_data = {
        'summary': 'This is a comprehensive summary of the test research paper.',
        'gaps': 'TITLE: Test Research Gap\nDescription: This is a test research gap description.',
        'sources': '1. Test Reference 1\n2. Test Reference 2'
    }
    
    # Add test data to cache
    CACHE[test_cache_id] = test_data
    CACHE[test_cache_id + "_processed"] = test_processed_data
    
    try:
        # Test PDF generation
        filepath, filename = generate_pdf_report(test_cache_id, "Test Research Report")
        
        if filepath and os.path.exists(filepath):
            print(f"✅ PDF export successful!")
            print(f"   File: {filename}")
            print(f"   Path: {filepath}")
            print(f"   Size: {os.path.getsize(filepath)} bytes")
            
            # Clean up test file
            os.remove(filepath)
            print("   Test file cleaned up.")
        else:
            print(f"❌ PDF export failed: {filename}")
            return False
            
    except Exception as e:
        print(f"❌ Error during PDF export test: {str(e)}")
        return False
    
    # Clean up test data
    del CACHE[test_cache_id]
    del CACHE[test_cache_id + "_processed"]
    
    print("✅ PDF export test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_pdf_export()
    sys.exit(0 if success else 1) 