# This code is part of Qiskit.
#
# (C) Copyright IBM 2020, 2023.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""The calculation of excited states via an Eigensolver algorithm."""

from __future__ import annotations

import logging

from typing import Union, Optional, Tuple

from qiskit.algorithms.eigensolvers import Eigensolver
from qiskit.opflow import PauliSumOp

from qiskit_nature.second_q.mappers import QubitConverter, QubitMapper
from qiskit_nature.second_q.operators import SparseLabelOp
from qiskit_nature.second_q.problems import BaseProblem
from qiskit_nature.second_q.problems import EigenstateResult

from .excited_states_solver import ExcitedStatesSolver
from .eigensolver_factories import EigensolverFactory

LOGGER = logging.getLogger(__name__)


class ExcitedStatesEigensolver(ExcitedStatesSolver):
    """The calculation of excited states via an Eigensolver algorithm."""

    def __init__(
        self,
        qubit_converter: QubitConverter | QubitMapper,
        solver: Union[Eigensolver, EigensolverFactory],
    ) -> None:
        """

        Args:
            qubit_converter: The ``QubitConverter`` or ``QubitMapper`` to use for mapping and symmetry
                reduction.
            solver: Minimum Eigensolver or MESFactory object.
        """
        self._qubit_converter = qubit_converter
        self._solver = solver

    @property
    def solver(self) -> Union[Eigensolver, EigensolverFactory]:
        """Returns the minimum eigensolver or factory."""
        return self._solver

    @solver.setter
    def solver(self, solver: Union[Eigensolver, EigensolverFactory]) -> None:
        """Sets the minimum eigensolver or factory."""
        self._solver = solver

    def get_qubit_operators(
        self,
        problem: BaseProblem,
        aux_operators: Optional[dict[str, Union[SparseLabelOp, PauliSumOp]]] = None,
    ) -> Tuple[PauliSumOp, Optional[dict[str, PauliSumOp]]]:
        # Note that ``aux_ops`` contains not only the transformed ``aux_operators`` passed by the
        # user but also additional ones from the transformation
        main_second_q_op, aux_second_q_ops = problem.second_q_ops()

        num_particles = getattr(problem, "num_particles", None)

        if isinstance(self._qubit_converter, QubitConverter):
            main_operator = self._qubit_converter.convert(
                main_second_q_op,
                num_particles=num_particles,
                sector_locator=problem.symmetry_sector_locator,
            )
            aux_ops = self._qubit_converter.convert_match(aux_second_q_ops)

        else:
            main_operator = self._qubit_converter.map(main_second_q_op)
            aux_ops = self._qubit_converter.map(aux_second_q_ops)

        if aux_operators is not None:
            for name_aux, aux_op in aux_operators.items():
                if isinstance(aux_op, SparseLabelOp):
                    if isinstance(self._qubit_converter, QubitConverter):
                        converted_aux_op = self._qubit_converter.convert_match(
                            aux_op, suppress_none=True
                        )
                    else:
                        converted_aux_op = self._qubit_converter.map(aux_op)
                else:
                    converted_aux_op = aux_op
                if name_aux in aux_ops.keys():
                    LOGGER.warning(
                        "The key '%s' was already taken by an internally constructed auxiliary "
                        "operator! The internal operator was overridden by the one provided manually. "
                        "If this was not the intended behavior, please consider renaming "
                        "this operator.",
                        name_aux,
                    )
                aux_ops[name_aux] = converted_aux_op

        if isinstance(self._solver, EigensolverFactory):
            # this must be called after transformation.transform
            self._solver = self._solver.get_solver(problem)

        # if the eigensolver does not support auxiliary operators, reset them
        if not self._solver.supports_aux_operators():
            aux_ops = None
        return main_operator, aux_ops

    def solve(
        self,
        problem: BaseProblem,
        aux_operators: Optional[dict[str, Union[SparseLabelOp, PauliSumOp]]] = None,
    ) -> EigenstateResult:
        """Compute Ground and Excited States properties.

        Args:
            problem: A class encoding a problem to be solved.
            aux_operators: Additional auxiliary operators to evaluate.

        Returns:
            An interpreted :class:`~.EigenstateResult`. For more information see also
            :meth:`~.BaseProblem.interpret`.
        """
        # get the operator and auxiliary operators, and transform the provided auxiliary operators
        # note that ``aux_operators`` contains not only the transformed ``aux_operators`` passed
        # by the user but also additional ones from the transformation

        main_operator, aux_ops = self.get_qubit_operators(problem, aux_operators)
        raw_es_result = self._solver.compute_eigenvalues(main_operator, aux_ops)  # type: ignore

        eigenstate_result = EigenstateResult.from_result(raw_es_result)
        result = problem.interpret(eigenstate_result)
        return result
