# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import jax.numpy as jn
import objax

from objax.typing import JaxArray
from typing import Callable, Tuple, Union


class MyRnnCell(objax.Module):
    """ Simple RNN cell."""

    def __init__(self, nin: int, nstate: int, activation: Callable = objax.functional.tanh):
        """Creates a MyRnnCell instance.
        Args:
            nin: dimension  of the input tensor.
            nstate: hidden state tensor has dimensions ``nin`` by ``nstate``.
            activation: activation function for the hidden state layer.
        """
        self.op = objax.nn.Sequential([objax.nn.Linear(nin + nstate, nstate),
                                       objax.nn.Linear(nstate, nstate), activation])

    def __call__(self, state: JaxArray, x: JaxArray) -> JaxArray:
        """Updates and returns hidden state based on input sequence ``x``and input ``state``."""
        return self.op(jn.concatenate((x, state), axis=0))


class FactorizedRnnCell(objax.Module):
    """ Factorized version of RNN cell."""

    def __init__(self, nin: int, nstate: int, activation: Callable = objax.functional.tanh):
        """Creates a MyRnnCell instance.
        Args:
            nin: dimension  of the input tensor.
            nstate: hidden state tensor has dimensions ``nin`` by ``nstate``.
            activation: activation function for the hidden state layer.
        """
        self.win = objax.nn.Linear(nin, nstate, use_bias=False)
        self.wn = objax.nn.Linear(nstate, nstate)
        self.activation = activation
        self.nstate = nstate

    def __call__(self, state: JaxArray, x: JaxArray) -> JaxArray:
        """Updates and returns hidden state based on input sequence ``x``and input ``state``."""
        self.factor = self.win(x)
        # TODO(aterzis): Replace with scan(?)
        output = []
        for i in range(x.shape[0]):
            state = self.activation(self.wn(state) + self.factor[i])
            output_i = jn.reshape(state, (1, self.nstate))
            output.append(output_i)
        outputs = jn.concatenate(output, axis=0)
        return jn.reshape(state, (1, self.nstate))


class DDLRnnCell(objax.Module):
    """ Another simple RNN cell."""

    def __init__(self, nin: int, nstate: int, activation: Callable = objax.functional.tanh):
        """ Creates a DDLRnnCell instance.
        Args:
            nin: dimension of the input tensor.
            nstate: hidden state tensor has dimensions ``nin`` by ``nstate``.
            activation: activation function for the hidden state layer.
        """
        self.wxh = objax.nn.Linear(nin, nstate, use_bias=False)
        self.whh = objax.nn.Linear(nstate, nstate)
        self.activation = activation

    def __call__(self, state: JaxArray, x: JaxArray) -> JaxArray:
        """Updates and returns hidden state based on input sequence ``x`` and input ``state``."""
        return self.activation(self.whh(state) + self.wxh(x))


def output_layer(state: int, nout: int):
    return objax.nn.Linear(state, nout)


class RNN(objax.Module):
    """Simple Recurrent Neural Network (RNN).
    State update is done by the provided RNN cell and output is generated by the
    provided output layer.
    """

    def __init__(self, cell: objax.Module, output_layer: Union[objax.Module, Callable]):
        """Creates an RNN instance.
        Args:
            cell: RNN cell.
            output_layer: output layer can be a function or another module.
        """
        self.cell = cell
        self.output_layer = output_layer  # Is it better inside or outside?

    def single(self, state_i: JaxArray, x_i: JaxArray) -> Tuple[JaxArray, JaxArray]:
        """Execute one step of the RNN.
        Args:
            state_i: current state.
            x_i: input.
        Returns:
            next state and next output.
        """
        next_state = self.cell(state_i, x_i)
        next_output = self.output_layer(next_state)
        return next_state, next_output

    def __call__(self, x: JaxArray, state: JaxArray) -> Tuple[JaxArray, JaxArray]:
        """Sequentially processes input to generate output.
        Args:
            x: input tensor with dimensions ``batch_size`` by ``sequence_length`` by  ``nin``
            state: Initial RNN state with dimensions ``batch_size`` by ``state``.
        Returns:
            Tuple with final RNN state and output with dimensions ``sequence_length`` by ``batch_size`` by ``nout``,
            where ``nout`` is the output dimension of the output layer (or ``state`` if there is no output layer).
        """
        final_state, output = objax.functional.scan(self.single, state, x.transpose((1, 0, 2)))
        return output, final_state


class VectorizedRNN(objax.Module):
    """Vectorized Recurrent Neural Network (RNN).
    State update is done by the provided RNN cell and output is generated by the
    provided output layer.
    """

    def __init__(self, cell: objax.Module, output_layer: Union[objax.Module, Callable]):
        """Creates an RNN instance.
        Args:
            cell: RNN cell.
            output_layer: output layer can be a function or another module.
        """
        self.cell = cell
        self.output_layer = output_layer  # Is it better inside or outside?

    def single(self, state_i: JaxArray, x_i: JaxArray) -> Tuple[JaxArray, JaxArray]:
        """Execute one step of the RNN.
        Args:
            state_i: current state.
            x_i: input.
        Returns:
            next state and next output.
        """
        next_state = self.cell(state_i, x_i)
        next_output = self.output_layer(next_state)
        return next_state, next_output

    def __call__(self, x: JaxArray, state: JaxArray) -> Tuple[JaxArray, JaxArray]:
        """Sequentially processes input to generate output.
        Args:
            x: input tensor with dimensions ``sequence_length`` by  ``nin``
            state: Initial RNN state with dimensions ``(nstate,)``.
        Returns:
            Tuple with final RNN state and output with dimensions ``sequence_length`` by ``nout``,
            where ``nout`` is the output dimension of the output layer (or ``nstate`` if there is no output layer).
        """
        final_state, output = objax.functional.scan(self.single, state, x)
        return output, final_state


class FactorizedRNN(objax.Module):
    """Factorized Recurrent Neural Network (RNN).
    State update is done by the provided RNN cell and output is generated by the
    provided output layer.
    """

    def __init__(self, cell: objax.Module, output_layer: Union[objax.Module, Callable]):
        """Creates an RNN instance.
        Args:
            cell: RNN cell.
            output_layer: output layer can be a function or another module.
        """
        self.cell = cell
        self.output_layer = output_layer  # Is it better inside or outside?


    def __call__(self, x: JaxArray, state: JaxArray) -> Tuple[JaxArray, JaxArray]:
        """Sequentially processes input to generate output.
        Args:
            x: input tensor with dimensions ``sequence_length`` by  ``nin``
            state: Initial RNN state with dimensions ``(state,)``.
        Returns:
            Tuple with final RNN state and output with dimensions ``sequence_length`` by ``nout``,
            where ``nout`` is the output dimension of the output layer (or ``state`` if there is no output layer).
        """
        out = self.cell(state, x)
        output = self.output_layer(out)
        return output, out[-1]

seq, ns, nin, nout, batch = 7, 10, 3, 4, 64

# RNN example
rnn_cell = DDLRnnCell(nin, ns)
out_layer = output_layer(ns, nout)

r = RNN(rnn_cell, out_layer)
x = objax.random.normal((batch, seq, nin))
s = jn.zeros((batch, ns))
y1 = r(x, s)

# Vectorized version
r = VectorizedRNN(rnn_cell, out_layer)
rnn_vec = objax.Vectorize(r, batch_axis=(0, 0))
y4 = rnn_vec(x, s)

assert jn.array_equal(y4[1], y1[1])
assert jn.array_equal(y4[0], y1[0].transpose((1, 0, 2)))

# Factorized version
factorized_cell = FactorizedRnnCell(nin, ns)
out = factorized_cell(s[0], x[0, :, :])
out2 = out_layer(out)

print("s.shape", s.shape)
print("out2.shape", out2.shape)

f = FactorizedRNN(factorized_cell, out_layer)
y5 = f(x[0, :, :], s[0])
print("y5[0].shape", y5[0].shape)
print("y5[1].shape", y5[1].shape)
assert jn.array_equal(y5[0], out2)
assert jn.array_equal(y5[1], out[-1])
