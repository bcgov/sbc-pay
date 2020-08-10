FROM python:3.8.5-buster

ARG python_version=3.6


# ========================================================================================================
# Install go-crond (from https://github.com/BCDevOps/go-crond)
#  - Adds some additional logging enhancements on top of the upstream project;
#    https://github.com/webdevops/go-crond
#
# CRON Jobs in OpenShift:
# - https://blog.danman.eu/cron-jobs-in-openshift/
#
# --------------------------------------------------------------------------------------------------------
ARG SOURCE_REPO=BCDevOps
ARG GOCROND_VERSION=0.6.2
RUN curl https://github.com/$SOURCE_REPO/go-crond/releases/download/$GOCROND_VERSION/go-crond-64-linux -s -L -o /usr/local/bin/go-crond
RUN chmod ug+x /usr/local/bin/go-crond
# ========================================================================================================

# Add a job user
ARG uid=1001
ARG user=sbc
RUN useradd -U -ms /bin/bash -u $uid $user \
    && usermod -a -G root $user


ENV HOME=/sbc
ENV PYENV_ROOT=$HOME/.venv
ENV APP_ROOT=$HOME \
    PATH=$PYENV_ROOT/bin:$PATH \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    SHELL=/bin/bash \
    PIP_NO_CACHE_DIR=off \
    PYTHON_VERSION=$python_version \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8

# Copy source code
ADD . $APP_ROOT
ADD ./docker-entrypoint.sh $APP_ROOT
ADD ./crontab $APP_ROOT
ADD ./run.sh $APP_ROOT
ADD ./requirements $APP_ROOT
ADD ./utils $APP_ROOT
ADD . $APP_ROOT

WORKDIR $APP_ROOT


RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt


# Set ownership and permissions
# Set scripts as executable (make files and python files do not have to be marked)
# Make /etc/passwd writable for the root group so an entry can be created for an OpenShift assigned user account.
RUN chown -R sbc:root $APP_ROOT \
    && chmod -R ug+rw $APP_ROOT \
    && chmod ug+x $APP_ROOT/*.sh \
    && chmod ug+x $APP_ROOT/run.sh \
    && chmod g+rw /etc/passwd \
    && chmod g-w $APP_ROOT/crontab

USER $user
ENTRYPOINT ["bash", "docker-entrypoint.sh"]