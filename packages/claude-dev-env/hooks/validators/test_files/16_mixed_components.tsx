// TEST: Mixed Component, PureComponent, and functional (should catch first two)
import React, { Component, PureComponent } from 'react';

class RegularComponent extends Component {
  render() {
    return <div>Regular</div>;
  }
}

class OptimizedComponent extends PureComponent {
  render() {
    return <div>Optimized</div>;
  }
}

const FunctionalComponent: React.FC = () => {
  return <div>Functional</div>;
};

export { RegularComponent, OptimizedComponent, FunctionalComponent };
