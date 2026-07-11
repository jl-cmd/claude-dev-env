// TEST: Multi-line class declaration (SHOULD BE CAUGHT but might not be)
import React from 'react';

class MyComponent
  extends React.Component {
  render() {
    return <div>Hello</div>;
  }
}

export default MyComponent;
