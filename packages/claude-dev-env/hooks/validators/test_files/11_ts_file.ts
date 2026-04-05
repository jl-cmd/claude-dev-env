// TEST: Class component in .ts file (SHOULD BE IGNORED - correct behavior)
import React from 'react';

class MyComponent extends React.Component {
  render() {
    return React.createElement('div', null, 'Hello');
  }
}

export default MyComponent;
