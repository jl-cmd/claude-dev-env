// TEST: Error boundary with getDerivedStateFromError (SHOULD BE ALLOWED)
import React from 'react';

class ErrorBoundary extends React.Component {
  static getDerivedStateFromError(error: Error) {
    return { hasError: true };
  }

  render() {
    return this.props.children;
  }
}

export default ErrorBoundary;
