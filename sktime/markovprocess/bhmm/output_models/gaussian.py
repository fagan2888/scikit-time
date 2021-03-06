# This file is part of BHMM (Bayesian Hidden Markov Models).
#
# Copyright (c) 2016 Frank Noe (Freie Universitaet Berlin)
# and John D. Chodera (Memorial Sloan-Kettering Cancer Center, New York)
#
# BHMM is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np

from sktime.markovprocess.bhmm.output_models.outputmodel import OutputModel
from ._bhmm_output_models import gaussian as gaussian



class GaussianOutputModel(OutputModel):
    """ HMM output probability model using 1D-Gaussians """

    def __init__(self, n_states, means=None, sigmas=None, ignore_outliers=True):
        """
        Create a 1D Gaussian output model.

        Parameters
        ----------
        n_states : int
            The number of output states.
        means : array_like of shape (n_states,), optional, default=None
            If specified, initialize the Gaussian means to these values.
        sigmas : array_like of shape (n_states,), optional, default=None
            If specified, initialize the Gaussian variances to these values.

        Examples
        --------

        Create an observation model.

        >>> output_model = GaussianOutputModel(n_states=3, means=[-1, 0, 1], sigmas=[0.5, 1, 2])

        """
        super(GaussianOutputModel, self).__init__(n_states=n_states, ignore_outliers=ignore_outliers)

        dtype = np.float64  # type for internal storage

        if means is not None:
            self._means = np.array(means, dtype=dtype)
            if self._means.shape != (n_states,):
                raise ValueError('means must have shape (%d,); instead got %s' % (n_states, str(self._means.shape)))
        else:
            self._means = np.zeros(n_states, dtype=dtype)

        if sigmas is not None:
            self._sigmas = np.array(sigmas, dtype=dtype).squeeze()
            if self._sigmas.shape != (n_states,):
                raise ValueError('sigmas must have shape (%d,); instead got %s' % (n_states, str(self._sigmas.shape)))
        else:
            self._sigmas = np.zeros(n_states, dtype=dtype)

    @property
    def model_type(self):
        r""" Model type. Returns 'gaussian' """
        return 'gaussian'

    @property
    def dimension(self):
        r""" Dimension of the Gaussian output model (currently 1) """
        return 1

    @property
    def means(self):
        r""" Mean values of Gaussians output densities """
        return self._means

    @property
    def sigmas(self):
        # TODO: Should we not rather give the variances? In the multidimensional case on usually uses the covariance
        # TODO:   matrix instead of its square root.
        r""" Standard deviations of Gaussian output densities """
        return self._sigmas

    def sub_output_model(self, states):
        return GaussianOutputModel(self._means[states], self._sigmas[states])

    def p_obs(self, obs, out=None):
        """
        Returns the output probabilities for an entire trajectory and all hidden states

        Parameters
        ----------
        oobs : ndarray((T), dtype=int)
            a discrete trajectory of length T

        Return
        ------
        p_o : ndarray (T,N)
            the probability of generating the symbol at time point t from any of the N hidden states

        Examples
        --------

        Generate an observation model and synthetic observation trajectory.

        >>> nobs = 1000
        >>> output_model = GaussianOutputModel(n_states=3, means=[-1, 0, +1], sigmas=[0.5, 1, 2])
        >>> s_t = np.random.randint(0, output_model.n_states, size=[nobs])
        >>> o_t = output_model.generate_observation_trajectory(s_t)

        Compute output probabilities for entire trajectory and all hidden states.

        >>> p_o = output_model.p_obs(o_t)

        """
        res = gaussian.p_obs(obs, self.means, self.sigmas, out=out)
        return self._handle_outliers(res)

    def fit(self, observations, weights):
        """
        Fits the output model given the observations and weights

        Parameters
        ----------
        observations : [ ndarray(T_k,) ] with K elements
            A list of K observation trajectories, each having length T_k and d dimensions
        weights : [ ndarray(T_k,n_states) ] with K elements
            A list of K weight matrices, each having length T_k
            weights[k][t,n] is the weight assignment from observations[k][t] to state index n

        Examples
        --------

        Generate an observation model and samples from each state.

        >>> ntrajectories = 3
        >>> nobs = 1000
        >>> output_model = GaussianOutputModel(n_states=3, means=[-1, 0, +1], sigmas=[0.5, 1, 2])
        >>> observations = [ np.random.randn(nobs) for _ in range(ntrajectories) ] # random observations
        >>> weights = [ np.random.dirichlet([2, 3, 4], size=nobs) for _ in range(ntrajectories) ] # random weights

        Update the observation model parameters my a maximum-likelihood fit.

        >>> output_model.fit(observations, weights)

        """
        # sizes
        N = self.n_states
        K = len(observations)

        # fit means
        self._means = np.zeros(N)
        w_sum = np.zeros(N)
        for k in range(K):
            # update nominator
            for i in range(N):
                self.means[i] += np.dot(weights[k][:, i], observations[k])
            # update denominator
            w_sum += np.sum(weights[k], axis=0)
        # normalize
        self._means /= w_sum

        # fit variances
        self._sigmas = np.zeros(N)
        w_sum = np.zeros(N)
        for k in range(K):
            # update nominator
            for i in range(N):
                Y = (observations[k] - self.means[i]) ** 2
                self.sigmas[i] += np.dot(weights[k][:, i], Y)
            # update denominator
            w_sum += np.sum(weights[k], axis=0)
        # normalize
        self._sigmas /= w_sum
        self._sigmas = np.sqrt(self.sigmas)
        if np.any(self._sigmas < np.finfo(self._sigmas.dtype).eps):
            raise RuntimeError('at least one sigma is too small to continue.')

    def sample(self, observations, prior=None):
        """
        Sample a new set of distribution parameters given a sample of observations from the given state.

        Both the internal parameters and the attached HMM model are updated.

        Parameters
        ----------
        observations :  [ numpy.array with shape (N_k,) ] with `n_states` elements
            observations[k] is a set of observations sampled from state `k`
        prior : object
            prior option for compatibility

        Examples
        --------

        Generate synthetic observations.

        >>> n_states = 3
        >>> nobs = 1000
        >>> output_model = GaussianOutputModel(n_states=n_states, means=[-1, 0, 1], sigmas=[0.5, 1, 2])
        >>> observations = [ output_model.generate_observations_from_state(state_index, nobs) for state_index in range(n_states) ]

        Update output parameters by sampling.

        >>> output_model.sample(observations)

        """
        for state_index in range(self.n_states):
            # Update state emission distribution parameters.

            observations_in_state = observations[state_index]
            # Determine number of samples in this state.
            nsamples_in_state = len(observations_in_state)

            # Skip update if no observations.
            if nsamples_in_state == 0:
                import warnings
                warnings.warn('Warning: State %d has no observations.' % state_index)
            if nsamples_in_state > 0:  # Sample new mu.
                self.means[state_index] = np.random.randn() * self.sigmas[state_index] / np.sqrt(
                    nsamples_in_state) + np.mean(observations_in_state)
            if nsamples_in_state > 1:  # Sample new sigma
                # This scheme uses the improper Jeffreys prior on sigma^2, P(mu, sigma^2) \propto 1/sigma
                chisquared = np.random.chisquare(nsamples_in_state - 1)
                sigmahat2 = np.mean((observations_in_state - self.means[state_index]) ** 2)
                self.sigmas[state_index] = np.sqrt(sigmahat2) / np.sqrt(chisquared / nsamples_in_state)

    def generate_observation_from_state(self, state_index):
        """
        Generate a single synthetic observation data from a given state.

        Parameters
        ----------
        state_index : int
            Index of the state from which observations are to be generated.

        Returns
        -------
        observation : float
            A single observation from the given state.

        Examples
        --------

        Generate an observation model.

        >>> output_model = GaussianOutputModel(n_states=2, means=[0, 1], sigmas=[1, 2])

        Generate sample from a state.

        >>> observation = output_model.generate_observation_from_state(0)

        """
        observation = self.sigmas[state_index] * np.random.randn() + self.means[state_index]
        return observation

    def generate_observations_from_state(self, state_index, nobs):
        """
        Generate synthetic observation data from a given state.

        Parameters
        ----------
        state_index : int
            Index of the state from which observations are to be generated.
        nobs : int
            The number of observations to generate.

        Returns
        -------
        observations : numpy.array of shape(nobs,)
            A sample of `nobs` observations from the specified state.

        Examples
        --------

        Generate an observation model.

        >>> output_model = GaussianOutputModel(n_states=2, means=[0, 1], sigmas=[1, 2])

        Generate samples from each state.

        >>> observations = [output_model.generate_observations_from_state(state_index, nobs=100) for state_index in range(output_model.n_states) ]

        """
        observations = self.sigmas[state_index] * np.random.randn(nobs) + self.means[state_index]
        return observations

    def generate_observation_trajectory(self, s_t):
        """
        Generate synthetic observation data from a given state sequence.

        Parameters
        ----------
        s_t : numpy.array with shape (T,) of int type
            s_t[t] is the hidden state sampled at time t

        Returns
        -------
        o_t : numpy.array with shape (T,) of type dtype
            o_t[t] is the observation associated with state s_t[t]

        Examples
        --------

        Generate an observation model and synthetic state trajectory.

        >>> nobs = 1000
        >>> output_model = GaussianOutputModel(n_states=3, means=[-1, 0, +1], sigmas=[0.5, 1, 2])
        >>> s_t = np.random.randint(0, output_model.n_states, size=[nobs])

        Generate a synthetic trajectory

        >>> o_t = output_model.generate_observation_trajectory(s_t)

        """

        # Determine number of samples to generate.
        T = s_t.shape[0]

        o_t = np.zeros([T], dtype=np.float64)
        for t in range(T):
            s = s_t[t]
            o_t[t] = self.sigmas[s] * np.random.randn() + self.means[s]
        return o_t
