// TEST: Class component with TypeScript generics (SHOULD BE CAUGHT but might not be)
import React from 'react';

interface Props {
  name: string;
}

class MyComponent extends React.Component<Props> {
  render() {
    return <div>{this.props.name}</div>;
  }
}

export default MyComponent;
