// TEST: Class component with Props and State generics (SHOULD BE CAUGHT but might not be)
import React from 'react';

interface Props {
  name: string;
}

interface State {
  count: number;
}

class MyComponent extends React.Component<Props, State> {
  render() {
    return <div>{this.props.name}</div>;
  }
}

export default MyComponent;
