// static/app.js

// Global variables for tracking execution time
let startTime = null;
let executionTimer = null;
let loadingBar = null;
let statusMessage = null;

// Initialize elements when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  loadingBar = document.getElementById("top-loading-bar");
  statusMessage = document.getElementById("status-message");
});

// Format time in a readable format
function formatTime(seconds) {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  }
}

// Update the timer display
function updateTimer() {
  if (startTime && statusMessage) {
    const elapsed = (Date.now() - startTime) / 1000;
    const currentText = statusMessage.textContent;
    
    // Check if this is a PDF upload
    if (currentText.includes('PDF') || currentText.includes('upload')) {
      statusMessage.textContent = `Processing PDF... ${formatTime(elapsed)}`;
    } else {
      statusMessage.textContent = `Executing... ${formatTime(elapsed)}`;
    }
  }
}

// Show error message immediately
function showError(errorMessage) {
  if (statusMessage) {
    const elapsed = startTime ? (Date.now() - startTime) / 1000 : 0;
    statusMessage.textContent = `${errorMessage} (${formatTime(elapsed)})`;
    statusMessage.style.color = "#ef4444"; // Red
    statusMessage.style.opacity = "1";
  }
  if (loadingBar) {
    loadingBar.style.backgroundColor = "#ef4444"; // Red
  }
}

// Start execution timer
function startExecutionTimer() {
  startTime = Date.now();
  if (loadingBar) {
    loadingBar.style.width = "0%";
    loadingBar.style.backgroundColor = "#3b82f6"; // Blue
  }
  if (statusMessage) {
    statusMessage.textContent = "Starting execution...";
    statusMessage.style.color = "#3b82f6";
    statusMessage.style.opacity = "1";
  }
  
  // Update timer every second
  executionTimer = setInterval(updateTimer, 1000);
}

// Complete execution timer
function completeExecutionTimer(success = true, errorMessage = null) {
  clearInterval(executionTimer);
  
  if (startTime) {
    const totalTime = (Date.now() - startTime) / 1000;
    
    if (success) {
      if (loadingBar) {
        loadingBar.style.width = "100%";
        loadingBar.style.backgroundColor = "#10b981"; // Green
      }
      if (statusMessage) {
        statusMessage.textContent = `Completed in ${formatTime(totalTime)}`;
        statusMessage.style.color = "#10b981";
      }
    } else {
      if (loadingBar) {
        loadingBar.style.width = "100%";
        loadingBar.style.backgroundColor = "#ef4444"; // Red
      }
      if (statusMessage) {
        const errorText = errorMessage || "An error occurred during execution";
        statusMessage.textContent = `${errorText} (${formatTime(totalTime)})`;
        statusMessage.style.color = "#ef4444";
      }
    }
    
    // Reset after 3 seconds
    setTimeout(() => {
      if (loadingBar) {
        loadingBar.style.width = "0%";
        loadingBar.style.backgroundColor = "#3b82f6";
      }
      if (statusMessage) {
        statusMessage.style.opacity = "0";
        setTimeout(() => {
          statusMessage.textContent = "";
        }, 300);
      }
      startTime = null;
    }, 3000);
  }
}

// HTMX event listeners
document.addEventListener("htmx:beforeRequest", (e) => {
  // Add loading class to the triggering button
  if (e.detail.elt.classList.contains("loading")) return;
  e.detail.elt.classList.add("loading");
  
  // Start the execution timer
  startExecutionTimer();
});

document.addEventListener("htmx:afterRequest", (e) => {
  // Remove loading class from the triggering button
  e.detail.elt.classList.remove("loading");
  
  // Check if the response indicates an error (4xx, 5xx status codes)
  if (e.detail.xhr && e.detail.xhr.status >= 400) {
    let errorMessage = "Server error occurred";
    try {
      if (e.detail.xhr.responseText) {
        const response = JSON.parse(e.detail.xhr.responseText);
        errorMessage = response.error || response.message || `HTTP ${e.detail.xhr.status} error`;
      } else {
        errorMessage = `HTTP ${e.detail.xhr.status} error`;
      }
    } catch (parseError) {
      errorMessage = `HTTP ${e.detail.xhr.status} error`;
    }
    
    // Show error immediately
    showError(errorMessage);
    
    // Complete timer with error after a short delay
    setTimeout(() => {
      completeExecutionTimer(false, errorMessage);
    }, 1000);
  } else {
    // Complete timer with success
    completeExecutionTimer(true);
  }
});

// Show errors immediately when they occur
document.addEventListener("htmx:responseError", (e) => {
  // Remove loading class from the triggering button
  if (e.detail.elt) {
    e.detail.elt.classList.remove("loading");
  }
  
  // Get error message from response or use default
  let errorMessage = "Request failed";
  try {
    if (e.detail.xhr.responseText) {
      const response = JSON.parse(e.detail.xhr.responseText);
      errorMessage = response.error || response.message || "Request failed";
    }
  } catch (parseError) {
    // If JSON parsing fails, use status text or default message
    errorMessage = e.detail.xhr.statusText || "Request failed";
  }
  
  // Show error immediately
  showError(errorMessage);
  
  // Complete timer with error after a short delay
  setTimeout(() => {
    completeExecutionTimer(false, errorMessage);
  }, 1000);
});

document.addEventListener("htmx:sendError", (e) => {
  // Remove loading class from the triggering button
  if (e.detail.elt) {
    e.detail.elt.classList.remove("loading");
  }
  
  // Show network error immediately
  showError("Network error - please check your connection");
  
  // Complete timer with network error after a short delay
  setTimeout(() => {
    completeExecutionTimer(false, "Network error - please check your connection");
  }, 1000);
});

// Additional error events for real-time error detection
document.addEventListener("htmx:beforeOnLoadError", (e) => {
  showError("Loading error occurred");
});

document.addEventListener("htmx:afterOnLoadError", (e) => {
  showError("Failed to load response");
});

document.addEventListener("htmx:beforeSwapError", (e) => {
  showError("Swap error occurred");
});

document.addEventListener("htmx:afterSwapError", (e) => {
  showError("Failed to update content");
});

// Monitor for timeout errors
document.addEventListener("htmx:beforeRequest", (e) => {
  // Set a timeout to detect hanging requests
  setTimeout(() => {
    if (startTime && statusMessage && statusMessage.textContent.includes("Executing")) {
      showError("Request is taking longer than expected");
    }
  }, 30000); // 30 seconds timeout
});

// Monitor for connection issues
let connectionCheckInterval = null;
document.addEventListener("htmx:beforeRequest", (e) => {
  // Start checking for connection issues
  connectionCheckInterval = setInterval(() => {
    if (!navigator.onLine) {
      showError("No internet connection");
    }
  }, 5000); // Check every 5 seconds
});

document.addEventListener("htmx:afterRequest", (e) => {
  // Clear connection check interval
  if (connectionCheckInterval) {
    clearInterval(connectionCheckInterval);
    connectionCheckInterval = null;
  }
});

// Listen for online/offline events
window.addEventListener('online', () => {
  if (startTime && statusMessage) {
    statusMessage.textContent = "Connection restored - continuing...";
    statusMessage.style.color = "#3b82f6";
  }
});

window.addEventListener('offline', () => {
  showError("Internet connection lost");
});

// PDF Upload Enhancement
document.addEventListener('DOMContentLoaded', () => {
  const pdfFileInput = document.querySelector('input[name="pdf_file"]');
  const uploadForm = document.querySelector('form[hx-post="/api/upload-pdf"]');
  
  if (pdfFileInput && uploadForm) {
    // File validation
    pdfFileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) {
        // Check file size (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
          showError("File too large. Please upload a PDF smaller than 10MB.");
          e.target.value = '';
          return;
        }
        
        // Check file type
        if (!file.type.includes('pdf')) {
          showError("Please select a valid PDF file.");
          e.target.value = '';
          return;
        }
        
        // Show file info
        if (statusMessage) {
          statusMessage.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)}MB)`;
          statusMessage.style.color = "#3b82f6";
          statusMessage.style.opacity = "1";
          
          setTimeout(() => {
            statusMessage.style.opacity = "0";
          }, 3000);
        }
      }
    });
    
    // Form submission enhancement
    uploadForm.addEventListener('submit', (e) => {
      const file = pdfFileInput.files[0];
      if (!file) {
        e.preventDefault();
        showError("Please select a PDF file to upload.");
        return;
      }
      
      // Start execution timer for upload
      startExecutionTimer();
    });
  }
  
  // PDF Export Enhancement
  document.addEventListener('htmx:afterRequest', (e) => {
    // Check if this is a PDF export request
    if (e.detail.xhr && e.detail.xhr.responseType === 'blob') {
      // This is a file download, show success message
      if (statusMessage) {
        statusMessage.textContent = "PDF report generated successfully!";
        statusMessage.style.color = "#10b981";
        statusMessage.style.opacity = "1";
        
        setTimeout(() => {
          statusMessage.style.opacity = "0";
        }, 3000);
      }
    }
  });
  
  // Additional PDF Export handling for different response types
  document.addEventListener('htmx:afterRequest', (e) => {
    // Check if this is a PDF export request by URL
    if (e.detail.xhr && e.detail.requestConfig && e.detail.requestConfig.path === '/api/export-pdf') {
      // Show success message for PDF export
      if (statusMessage) {
        statusMessage.textContent = "PDF report generated successfully!";
        statusMessage.style.color = "#10b981";
        statusMessage.style.opacity = "1";
        
        setTimeout(() => {
          statusMessage.style.opacity = "0";
        }, 3000);
      }
    }
  });
  
  // Enhanced PDF Export detection for form submissions
  document.addEventListener('htmx:afterRequest', (e) => {
    // Check if this is a PDF export request by form action
    if (e.detail.elt && e.detail.elt.tagName === 'FORM' && 
        e.detail.elt.getAttribute('hx-post') === '/api/export-pdf') {
      // Show success message for PDF export
      if (statusMessage) {
        statusMessage.textContent = "PDF report generated successfully!";
        statusMessage.style.color = "#10b981";
        statusMessage.style.opacity = "1";
        
        setTimeout(() => {
          statusMessage.style.opacity = "0";
        }, 3000);
      }
    }
  });
  
  // Enhanced PDF Export detection for custom export
  document.addEventListener('htmx:afterRequest', (e) => {
    // Check if this is a PDF export request by form action
    if (e.detail.elt && e.detail.elt.tagName === 'FORM' && 
        e.detail.elt.getAttribute('hx-post') === '/api/export-pdf-custom') {
      // Show success message for PDF export
      if (statusMessage) {
        statusMessage.textContent = "PDF report generated successfully!";
        statusMessage.style.color = "#10b981";
        statusMessage.style.opacity = "1";
        
        setTimeout(() => {
          statusMessage.style.opacity = "0";
        }, 3000);
      }
    }
  });
  
  // Auto-suggest filenames for PDF export
  document.addEventListener('htmx:afterRequest', (e) => {
    // Check if we're on a results page and need to set up filename suggestions
    if (e.detail.elt && e.detail.elt.tagName === 'FORM' && 
        (e.detail.elt.getAttribute('hx-post') === '/api/step2' || 
         e.detail.elt.getAttribute('hx-post') === '/api/upload-pdf')) {
      
      // Wait for the DOM to update
      setTimeout(() => {
        const filenameInputs = document.querySelectorAll('input[name="custom_filename"]');
        filenameInputs.forEach(input => {
          // Generate suggested filename based on page content
          const pageTitle = document.querySelector('h2')?.textContent || 'Research_Analysis';
          const suggestedName = pageTitle
            .replace(/[^a-zA-Z0-9\s]/g, '') // Remove special characters
            .replace(/\s+/g, '_') // Replace spaces with underscores
            .toLowerCase();
          
          // Set placeholder with suggestion
          input.placeholder = `e.g., ${suggestedName}_report.pdf`;
          
          // Add click handler to auto-fill
          input.addEventListener('click', () => {
            if (!input.value) {
              input.value = `${suggestedName}_report.pdf`;
            }
          });
        });
      }, 100);
    }
  });
});
