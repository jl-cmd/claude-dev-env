// TEST: Heavily indented class component (SHOULD BE CAUGHT)
import React from 'react';

function createComponent() {
      class MyComponent extends React.Component {
        render() {
          return <div>Hello</div>;
        }
      }
  return MyComponent;
}

export default createComponent();
