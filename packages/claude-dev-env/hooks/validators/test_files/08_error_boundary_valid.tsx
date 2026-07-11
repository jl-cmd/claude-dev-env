// TEST: Valid error boundary (SHOULD BE ALLOWED)
import React from 'react';

class ErrorBoundary extends React.Component {
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error(error, errorInfo);
  }

  render() {
    return this.props.children;
  }
}

export default ErrorBoundary;
