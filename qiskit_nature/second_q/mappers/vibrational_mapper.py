# This code is part of Qiskit.
#
# (C) Copyright IBM 2021, 2023.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Vibrational Mapper."""

from abc import abstractmethod

from qiskit.opflow import PauliSumOp

from qiskit_nature.second_q.operators import VibrationalOp

from .qubit_mapper import QubitMapper


class VibrationalMapper(QubitMapper):
    """Mapper of Vibrational Operator to Qubit Operator"""

    @abstractmethod
    def _map_single(self, second_q_op: VibrationalOp) -> PauliSumOp:
        """Maps a :class:`~qiskit_nature.second_q.operators.VibrationalOp`
        to a `PauliSumOp`.

        Args:
            second_q_op: the `VibrationalOp` to be mapped.

        Returns:
            The `PauliSumOp` corresponding to the problem-Hamiltonian in the qubit space.
        """
        raise NotImplementedError()
